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
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from .profiles import CharacterProfile


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
    profile: CharacterProfile | None = None

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


class ReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    naturalness: str = Field(min_length=1, max_length=1000)
    persona: str = Field(min_length=1, max_length=1000)
    continuity: str = Field(min_length=1, max_length=1000)
    credibility: str = Field(min_length=1, max_length=1000)
    empathy: str = Field(min_length=1, max_length=1000)
    boundary: str = Field(min_length=1, max_length=1000)

    @field_validator("*")
    @classmethod
    def concrete(cls, value):
        if not value.strip():
            raise ValueError("Each review dimension needs an observed quotation or concrete evidence")
        return value.strip()


class RestoreCharacterInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: StrictInt = Field(ge=1)


class ReviewInput(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    run_id: str | None = Field(default=None, max_length=80)
    schema_version: Literal[1, 2] = 1
    persona_score: StrictInt = Field(ge=1, le=5)
    empathy_score: StrictInt = Field(ge=1, le=5)
    memory_score: StrictInt | None = Field(default=None, ge=1, le=5)
    naturalness_score: StrictInt | None = Field(default=None, ge=1, le=5)
    continuity_score: StrictInt | None = Field(default=None, ge=1, le=5)
    credibility_score: StrictInt | None = Field(default=None, ge=1, le=5)
    boundary_score: StrictInt | None = Field(default=None, ge=1, le=5)
    evidence: ReviewEvidence | None = None
    note: str = Field(min_length=1, max_length=2000)

    @field_validator("schema_version", mode="before")
    @classmethod
    def explicit_version(cls, value):
        if type(value) is not int:
            raise ValueError("Review schema version must be an integer")
        return value

    @model_validator(mode="after")
    def version_contract(self):
        extra_scores = (self.naturalness_score, self.continuity_score, self.credibility_score, self.boundary_score)
        if self.schema_version == 2 and (any(score is None for score in extra_scores) or self.evidence is None):
            raise ValueError("Version 2 reviews require all six scores and their evidence")
        if self.schema_version == 1 and (self.memory_score is None or any(score is not None for score in extra_scores) or self.evidence is not None):
            raise ValueError("Version 1 reviews require the original three scores only")
        return self

    @field_validator("note")
    @classmethod
    def evidence_required(cls, value):
        if not value.strip():
            raise ValueError("A concrete review note is required")
        return value.strip()


class ProvisionUserInput(Credentials):
    adult_confirmed: Literal[True]


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


def admin_router(store, settings, user_auth=None, budgets=None):
    router = APIRouter(prefix="/api/admin", tags=["management"])
    auth = AdminAuth(store, settings.admin_token_minutes)

    async def credentials(request: Request):
        from pydantic import ValidationError
        try:
            return Credentials.model_validate(await request.json())
        except (ValidationError, ValueError, TypeError):
            raise HTTPException(422, "A valid username and a 12–128 character password are required.") from None

    def require_review_access(sid):
        session = store.session(sid)
        if not session:
            raise HTTPException(404, "Session not found")
        if settings.auth_mode == "accounts" and (not session["owner_user_id"] or not session["review_access_allowed"]):
            raise HTTPException(403, "The user has not allowed reviewer access to this conversation.")

    @router.get("/setup-status")
    async def setup_status():
        return {"initialized": bool(store.administrator()), "can_initialize": not bool(settings.allowed_hosts)}

    @router.post("/bootstrap")
    async def bootstrap(request: Request, body=Depends(credentials)):
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
    async def login(request: Request, body=Depends(credentials)):
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
        return {**store.overview(), "scope": "aggregate counts on this server; dialogue access requires user permission in accounts mode",
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

    @router.get("/characters/{cid}/revisions", dependencies=[Depends(auth.require)])
    async def character_history(cid: str):
        if not store.character(cid):
            raise HTTPException(404, "Character not found")
        return {"items": store.character_revisions(cid)}

    @router.post("/characters/{cid}/restore", dependencies=[Depends(auth.require)])
    async def restore_character(cid: str, body: RestoreCharacterInput):
        if not store.character(cid):
            raise HTTPException(404, "Character not found")
        try:
            return store.restore_character(cid, body.revision)
        except ValueError:
            raise HTTPException(404, "Character revision not found") from None

    @router.get("/sessions", dependencies=[Depends(auth.require)])
    async def sessions():
        return {"items": store.list_sessions(), "limit": 100, "scope": "summary only"}

    @router.get("/sessions/{sid}")
    async def session_details(sid: str, account=Depends(auth.require)):
        require_review_access(sid)
        rows = store.list_sessions([sid])
        if not rows:
            raise HTTPException(404, "Session not found")
        store.audit_event("admin:" + account["sub"], "reviewer_read", sid)
        return {"session": rows[0], "messages": store.history(sid, 100), "memories": store.memories(sid),
                "turns": store.turn_metadata(sid), "scope": "up to 100 recent messages and 100 recent turns"}

    @router.get("/reviews", dependencies=[Depends(auth.require)])
    async def reviews():
        return {"items": store.reviews(permitted_only=settings.auth_mode == "accounts"), "limit": 100}

    @router.post("/reviews")
    async def add_review(body: ReviewInput, account=Depends(auth.require)):
        require_review_access(body.session_id)
        try:
            result = store.save_review(body.model_dump())
            store.audit_event("admin:" + account["sub"], "review_added", body.session_id)
            return result
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @router.post("/users")
    async def provision_user(request: Request, account=Depends(auth.require)):
        # Manual validation avoids echoing passwords in FastAPI's default 422 response.
        from pydantic import ValidationError
        try:
            body = ProvisionUserInput.model_validate(await request.json())
        except (ValidationError, ValueError, TypeError):
            raise HTTPException(422, "Username, a 12–128 character password, and adult confirmation are required.") from None
        if settings.auth_mode != "accounts" or user_auth is None:
            raise HTTPException(409, "User accounts are not enabled on this server.")
        try:
            result = await user_auth.provision(body.username, body.password, body.adult_confirmed)
        except ValueError:
            raise HTTPException(422, "The account could not be provisioned; check the username and credentials.") from None
        store.audit_event("admin:" + account["sub"], "user_provisioned", result["id"])
        return {"user": result}

    @router.get("/operations", dependencies=[Depends(auth.require)])
    async def operations():
        return {"budgets": budgets.snapshot() if budgets else {}, "audit": store.audit_events(100),
                "audit_retention_days": settings.audit_retention_days,
                "scope": "bounded process metrics and redacted audit metadata; no dialogue or tool content"}

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
                "credentials_set": bool(settings.api_key), "quality_evidence": "pending human-reviewed companion-quality evaluation"}

    return router
