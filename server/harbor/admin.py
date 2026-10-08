"""A small, authenticated management plane for this single-owner prototype."""
import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)


class CharacterInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    tagline: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=600)
    system_prompt: str = Field(min_length=1, max_length=6000)
    greeting: str = Field(min_length=1, max_length=600)
    accent_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    avatar_style: Literal["nova", "sage", "ember"] = "nova"
    enabled: bool = True

    @field_validator("name", "tagline", "description", "system_prompt", "greeting")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Must not be blank")
        return value

    @field_validator("name")
    @classmethod
    def single_line(cls, value):
        if any(char in value for char in "\r\n\x00"):
            raise ValueError("Character name must be a single line")
        return value


class ReviewInput(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    run_id: str | None = Field(default=None, max_length=80)
    persona_score: int = Field(ge=1, le=5)
    empathy_score: int = Field(ge=1, le=5)
    memory_score: int = Field(ge=1, le=5)
    note: str = Field(min_length=1, max_length=2000)

    @field_validator("note")
    @classmethod
    def evidence_required(cls, value):
        if not value.strip():
            raise ValueError("A concrete review note is required")
        return value.strip()


def encode(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()


class AdminAuth:
    def __init__(self, store, minutes):
        self.store = store
        self.ttl = minutes * 60
        self.secret = secrets.token_bytes(32)
        self.attempts = defaultdict(deque)
        self.revoked = {}
        self.bootstrap_lock = asyncio.Lock()

    def rate_limit(self, request):
        # This deliberately uses the socket address, not untrusted forwarding headers.
        host = request.client.host if request.client else "unknown"
        stamp = time.monotonic()
        queue = self.attempts[host]
        while queue and queue[0] < stamp - 60:
            queue.popleft()
        if len(queue) >= 10:
            raise HTTPException(429, "Too many login attempts; try again in one minute.")
        queue.append(stamp)

    def issue(self, username):
        payload = encode(json.dumps({"sub": username, "exp": int(time.time()) + self.ttl,
                                     "jti": secrets.token_hex(16), "type": "admin"}, separators=(",", ":")).encode())
        signature = encode(hmac.new(self.secret, payload.encode(), hashlib.sha256).digest())
        return {"token": payload + "." + signature, "expires_in": self.ttl}

    async def require(self, request: Request):
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer "):
            raise HTTPException(401, "Administrator login required.")
        try:
            payload, signature = value[7:].split(".")
            expected = encode(hmac.new(self.secret, payload.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(expected, signature):
                raise ValueError("Signature mismatch")
            data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            if data.get("type") != "admin" or not isinstance(data.get("exp"), int) or data["exp"] <= time.time():
                raise ValueError("Expired token")
            self.revoked = {key: expiry for key, expiry in self.revoked.items() if expiry > time.time()}
            if data.get("jti") in self.revoked:
                raise ValueError("Logged out")
            account = self.store.administrator()
            if not account or data.get("sub") != account["username"] or not isinstance(data.get("jti"), str):
                raise ValueError("Unknown administrator")
            return data
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise HTTPException(401, "Administrator login required.") from None


def admin_router(store, settings):
    router = APIRouter(prefix="/api/admin", tags=["management"])
    auth = AdminAuth(store, settings.admin_token_minutes)

    @router.get("/setup-status")
    async def setup_status():
        return {"initialized": bool(store.administrator()), "can_initialize": not bool(settings.allowed_hosts)}

    @router.post("/bootstrap")
    async def bootstrap(body: Credentials, request: Request):
        # The first administrator can only be created on the backend machine.
        if (settings.allowed_hosts or not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}
                or request.url.hostname not in {"127.0.0.1", "localhost", "testserver"}):
            raise HTTPException(403, "Initialize the administrator on the server's localhost browser.")
        auth.rate_limit(request)
        async with auth.bootstrap_lock:
            if store.administrator():
                raise HTTPException(409, "Administrator is already initialized; use login.")
            salt = secrets.token_hex(16)
            digest = await run_in_threadpool(password_digest, body.password, salt)
            try:
                store.create_administrator(body.username, digest, salt)
            except sqlite3.IntegrityError:
                raise HTTPException(409, "Administrator is already initialized; use login.") from None
            return auth.issue(body.username)

    @router.post("/login")
    async def login(body: Credentials, request: Request):
        auth.rate_limit(request)
        account = store.administrator()
        # A fixed dummy salt keeps unknown-user requests on the same slow path.
        digest = await run_in_threadpool(password_digest, body.password, account["salt"] if account else "00" * 16)
        if not account or not hmac.compare_digest(digest, account["password_hash"]) or not hmac.compare_digest(body.username, account["username"]):
            raise HTTPException(401, "Invalid administrator credentials.")
        return auth.issue(body.username)

    @router.post("/logout")
    async def logout(account=Depends(auth.require)):
        auth.revoked[account["jti"]] = account["exp"]
        return {"ok": True}

    @router.get("/overview", dependencies=[Depends(auth.require)])
    async def overview():
        return {**store.overview(), "scope": "all sessions on this single-owner server",
                "quality_evidence": "Human reviews are annotations; mock scores do not establish model quality."}

    @router.get("/characters", dependencies=[Depends(auth.require)])
    async def characters():
        return {"items": store.characters()}

    @router.post("/characters", dependencies=[Depends(auth.require)])
    async def create_character(body: CharacterInput):
        if len(store.characters()) >= 30:
            raise HTTPException(422, "Character limit reached for this prototype.")
        return store.save_character(body.model_dump())

    @router.put("/characters/{cid}", dependencies=[Depends(auth.require)])
    async def update_character(cid: str, body: CharacterInput):
        if not store.character(cid):
            raise HTTPException(404, "Character not found")
        return store.save_character(body.model_dump(), cid)

    @router.get("/sessions", dependencies=[Depends(auth.require)])
    async def sessions():
        return {"items": store.list_sessions(), "limit": 100, "scope": "summary only"}

    @router.get("/sessions/{sid}", dependencies=[Depends(auth.require)])
    async def session_details(sid: str):
        rows = store.list_sessions([sid])
        if not rows:
            raise HTTPException(404, "Session not found")
        return {"session": rows[0], "messages": store.history(sid, 100), "memories": store.memories(sid),
                "turns": store.turn_metadata(sid), "scope": "up to 100 recent messages and 100 recent turns"}

    @router.get("/reviews", dependencies=[Depends(auth.require)])
    async def reviews():
        return {"items": store.reviews(), "limit": 100}

    @router.post("/reviews", dependencies=[Depends(auth.require)])
    async def add_review(body: ReviewInput):
        try:
            return store.save_review(body.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @router.get("/provider-status", dependencies=[Depends(auth.require)])
    async def provider_status():
        try:
            url = urlsplit(settings.api_base)
            host = url.hostname or ""
            if ":" in host:
                host = "[" + host + "]"
            netloc = host + (f":{url.port}" if url.port is not None else "")
            safe_base = urlunsplit((url.scheme, netloc, url.path, "", "")) if settings.api_base else ""
        except ValueError:
            safe_base = ""
        return {"provider": settings.provider, "configured": settings.provider == "mock" or bool(settings.api_base and settings.model and settings.api_key),
                "model": settings.model if settings.provider != "mock" else None, "api_base": safe_base,
                "credentials_set": bool(settings.api_key), "quality_evidence": "pending real-model evaluation"}

    return router
