import asyncio
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import Agent
from .config import ROOT, Settings
from .providers import CompatibleProvider, MockProvider, ProviderError
from .store import Store


class NewSession(BaseModel):
    adult_confirmed: bool
    mode: Literal["friend", "gentle_romance"] = "friend"


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=300)


def create_app(settings=None, provider=None):
    settings = settings or Settings.from_env()
    if settings.provider not in {"mock", "openai_compatible"}:
        raise ValueError("Unknown HARBOR_PROVIDER")
    store = Store(settings.db_path)
    provider = provider or (MockProvider() if settings.provider == "mock" else CompatibleProvider(settings))
    agent = Agent(store, provider, settings)
    locks = {}
    app = FastAPI(title="HarborCompanion", version="0.1.0")
    app.state.store = store

    @app.middleware("http")
    async def local_browser_guard(request: Request, call_next):
        # No cookies or public auth yet. Reject browser requests from unrelated origins.
        origin = request.headers.get("origin")
        host = request.headers.get("host", "")
        allowed = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765", "http://localhost:8765"}
        if request.url.path.startswith("/api/") and origin and origin not in allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Origin not allowed for local demo."}, status_code=403)
        if request.url.path.startswith("/api/") and host.split(":")[0] not in {"127.0.0.1", "localhost", "testserver"}:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "This prototype is restricted to localhost."}, status_code=403)
        return await call_next(request)

    def require(sid):
        session = store.session(sid)
        if not session:
            raise HTTPException(404, "Session not found")
        return session

    def lock(sid):
        return locks.setdefault(sid, asyncio.Lock())

    @app.get("/api/status")
    async def status():
        ready = settings.provider == "mock" or bool(settings.api_base and settings.api_key and settings.model)
        return {"provider": settings.provider, "configured": ready, "model": settings.model if settings.provider != "mock" else None,
                "stage": "framework prototype", "quality_evidence": "pending real-model evaluation"}

    @app.post("/api/sessions")
    async def new_session(body: NewSession):
        if not body.adult_confirmed:
            raise HTTPException(422, "Adult confirmation is required for this prototype.")
        return store.create(body.mode)

    @app.get("/api/sessions/{sid}")
    async def read_session(sid: str):
        return {**require(sid), "messages": store.history(sid, 100), "memories": store.memories(sid), "insights": store.insights(sid)}

    @app.post("/api/sessions/{sid}/chat")
    async def chat(sid: str, body: ChatInput):
        async with lock(sid):
            require(sid)
            cached = store.cached(sid, body.request_id)
            if cached:
                return cached
            text = body.message.strip()
            if not text:
                raise HTTPException(422, "Message must not be blank")
            try:
                result = await agent.run(sid, text)
            except (ProviderError, TimeoutError):
                raise HTTPException(502, "Model could not complete the turn. No mock fallback or half-turn was saved.") from None
            return store.commit_turn(sid, body.request_id, text, result)

    @app.post("/api/sessions/{sid}/memories")
    async def add_memory(sid: str, body: MemoryInput):
        async with lock(sid):
            require(sid)
            content = body.content.strip()
            if not content:
                raise HTTPException(422, "Memory must not be blank")
            return {"id": store.memory_add(sid, content), "status": "approved"}

    @app.post("/api/sessions/{sid}/memories/{mid}/{action}")
    async def memory_action(sid: str, mid: str, action: Literal["approve", "delete"]):
        async with lock(sid):
            require(sid)
            if not store.memory_action(sid, mid, action):
                raise HTTPException(404, "Memory not found")
            return {"ok": True}

    @app.delete("/api/sessions/{sid}/history")
    async def clear_history(sid: str):
        async with lock(sid):
            require(sid)
            store.clear_history(sid)
            return {"ok": True, "approved_memories_retained": True}

    @app.delete("/api/sessions/{sid}")
    async def delete_session(sid: str):
        async with lock(sid):
            require(sid)
            store.delete(sid)
            return {"ok": True}

    dist = ROOT / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


app = create_app()
