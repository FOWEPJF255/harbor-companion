"""Single-process budgets and redacted run audit for the controlled demo."""
import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import HTTPException


class RunBudgets:
    def __init__(self, settings):
        self.settings = settings
        self.requests = defaultdict(deque)
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_runs)
        self.active = 0
        self.rejected = 0

    def accept(self, actor):
        stamp = time.monotonic()
        # Remove expired identities to keep a stream of anonymous sessions bounded.
        for key in list(self.requests):
            queue = self.requests[key]
            while queue and queue[0] <= stamp - 60:
                queue.popleft()
            if not queue:
                self.requests.pop(key, None)
        if actor not in self.requests and len(self.requests) >= 10_000:
            self.rejected += 1
            raise HTTPException(429, "Request budget unavailable; try again later.", headers={"Retry-After": "60"})
        queue = self.requests[actor]
        if len(queue) >= self.settings.chat_requests_per_minute:
            self.rejected += 1
            raise HTTPException(429, "Chat request limit reached; try again in one minute.", headers={"Retry-After": "60"})
        queue.append(stamp)

    @asynccontextmanager
    async def slot(self):
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=self.settings.run_queue_timeout)
        except TimeoutError:
            self.rejected += 1
            raise HTTPException(429, "All model run slots are busy; try again later.", headers={"Retry-After": "2"}) from None
        self.active += 1
        try:
            yield
        finally:
            self.active -= 1
            self.semaphore.release()

    def snapshot(self):
        return {"active_runs": self.active, "max_concurrent_runs": self.settings.max_concurrent_runs,
                "requests_per_actor_per_minute": self.settings.chat_requests_per_minute,
                "rejected_since_start": self.rejected, "scope": "single process; resets on restart"}
