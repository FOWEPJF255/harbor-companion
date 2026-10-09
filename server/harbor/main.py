import asyncio
import secrets
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, ConfigDict, Field

from .admin import admin_router
from .agent import Agent, AgentFailure
from .data_agent import analyze
from .characters import public_character
from .config import ROOT, Settings
from .providers import CompatibleProvider, MockProvider, ProviderError
from .store import Store
from .user_auth import UserAuth, user_router
from .operations import RunBudgets


class NewSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adult_confirmed: bool
    mode: Literal["friend", "gentle_romance"] = "friend"
    character_id: str = Field(default="nova", min_length=1, max_length=80)
    memory_from_session_id: str | None = Field(default=None, min_length=1, max_length=80)
    language: Literal["zh", "en"] = "zh"


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    language: Literal["zh", "en"] | None = None


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=300)


class MemoryCorrectionInput(MemoryInput):
    model_config = ConfigDict(extra="forbid")
    approve_pending: bool = False


class AnalysisInput(BaseModel):
    question: str = Field(min_length=1, max_length=300)


class ReviewAccessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: bool


def create_app(settings=None, provider=None):
    settings = settings or Settings.from_env()
    if settings.provider not in {"mock", "openai_compatible"}:
        raise ValueError("Unknown HARBOR_PROVIDER")
    if settings.auth_mode not in {"local_demo", "accounts"}:
        raise ValueError("HARBOR_AUTH_MODE must be local_demo or accounts")
    if settings.allowed_hosts and settings.auth_mode != "accounts":
        raise ValueError("Additional hosts require HARBOR_AUTH_MODE=accounts.")
    if settings.allowed_hosts and len(settings.client_token) < 32:
        raise ValueError("Additional hosts require a HARBOR_CLIENT_TOKEN of at least 32 characters.")
    if any("/" in host or "*" in host or ":" in host for host in settings.allowed_hosts):
        raise ValueError("HARBOR_ALLOWED_HOSTS must contain exact hostnames, without protocols or wildcards.")
    for origin in settings.allowed_origins:
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("Additional browser origins must be exact HTTPS origins, without paths or credentials.")
    store = Store(settings.db_path)
    store.prune_audit(settings.audit_retention_days)
    user_auth = UserAuth(store, settings)
    budgets = RunBudgets(settings)
    provider = provider or (MockProvider() if settings.provider == "mock" else CompatibleProvider(settings))
    agent = Agent(store, provider, settings)
    locks = {}
    app = FastAPI(title="HarborCompanion", version="0.4.0")
    app.state.store = store
    app.state.user_auth = user_auth
    app.state.budgets = budgets
    app.state.agent = agent
    app.state.session_locks = locks

    @app.middleware("http")
    async def local_browser_guard(request: Request, call_next):
        # Anonymous capabilities remain loopback only. Remote access also requires user accounts.
        origin = request.headers.get("origin")
        host = request.url.hostname
        allowed = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765", "http://localhost:8765",
                   "https://localhost", "capacitor://localhost", *settings.allowed_origins}
        if host in {"127.0.0.1", "localhost"}:
            allowed.add(str(request.base_url).rstrip("/"))
        if request.url.path.startswith("/api/") and origin and origin not in allowed:
            return JSONResponse({"detail": "Origin not allowed for this demo."}, status_code=403, headers={"Cache-Control": "no-store"})
        if request.url.path.startswith("/api/") and host not in {"127.0.0.1", "localhost", "testserver", *settings.allowed_hosts}:
            return JSONResponse({"detail": "This prototype is restricted to configured hosts."}, status_code=403, headers={"Cache-Control": "no-store"})
        public_paths = {"/api/status", "/api/health", "/api/characters", "/api/admin/setup-status"}
        if settings.client_token and request.url.path.startswith("/api/") and request.url.path not in public_paths:
            supplied = request.headers.get("x-harbor-access", "")
            if not secrets.compare_digest(supplied, settings.client_token):
                return JSONResponse({"detail": "Demo access code is required."}, status_code=403, headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/") or request.url.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(CORSMiddleware,
                       allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8765", "http://localhost:8765",
                                      "https://localhost", "capacitor://localhost", *settings.allowed_origins],
                       allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["Content-Type", "Authorization", "X-Harbor-Access"])
    app.include_router(user_router(user_auth))
    app.include_router(admin_router(store, settings, user_auth, budgets))

    async def principal(request: Request):
        return await user_auth.require(request) if settings.auth_mode == "accounts" else None

    def actor(owner, request=None):
        return owner["id"] if owner else "local:" + (request.client.host if request and request.client else "unknown")

    def session_payload(session):
        return {**{key: value for key, value in session.items() if key not in {"character_prompt", "memory_scope", "owner_user_id"}},
                "review_access_allowed": bool(session["review_access_allowed"])}

    def require(sid, owner):
        session = store.session(sid)
        if not session or session["owner_user_id"] != (owner["id"] if owner else None):
            raise HTTPException(404, "Session not found")
        return session

    def lock(sid):
        return locks.setdefault(sid, asyncio.Lock())

    @asynccontextmanager
    async def locked(sid):
        mutex = lock(sid)
        try:
            await asyncio.wait_for(mutex.acquire(), timeout=settings.run_queue_timeout)
        except TimeoutError:
            raise HTTPException(429, "This session is busy; try again later.", headers={"Retry-After": "2"}) from None
        try:
            yield
        finally:
            mutex.release()

    @app.get("/api/status")
    async def status():
        ready = settings.provider == "mock" or bool(settings.api_base and settings.api_key and settings.model)
        return {"provider": settings.provider, "configured": ready, "model": settings.model if settings.provider != "mock" else None,
                "stage": "v0.4 controlled app + account foundation", "quality_evidence": "pending human-reviewed companion-quality evaluation",
                "access_code_required": bool(settings.client_token), "auth_mode": settings.auth_mode,
                "registration_enabled": settings.auth_mode == "accounts" and settings.registration_enabled}

    @app.get("/api/health")
    async def health():
        try:
            with store.connect() as db:
                db.execute("SELECT 1").fetchone()
        except Exception:
            return JSONResponse({"status": "not_ready", "database": "unavailable"}, status_code=503)
        return {"status": "ready", "database": "ready", "provider": settings.provider,
                "provider_configured": settings.provider == "mock" or bool(settings.api_base and settings.api_key and settings.model),
                "provider_probe": "not performed by this endpoint"}

    @app.get("/api/characters")
    async def characters():
        return {"items": [public_character(item) for item in store.characters(public=True)]}

    @app.get("/api/sessions")
    async def sessions(ids: str = "", cursor: str | None = Query(default=None, max_length=90), owner=Depends(principal)):
        if owner:
            try:
                return store.account_sessions(owner["id"], cursor)
            except ValueError:
                raise HTTPException(422, "Invalid session cursor") from None
        # Clients can enumerate only capability handles already present on their device.
        handles = list(dict.fromkeys(x for x in ids.split(",") if x))
        if len(handles) > 20 or any(len(handle) > 80 for handle in handles):
            raise HTTPException(422, "Too many session handles")
        visible = [sid for sid in handles if (store.session(sid) or {}).get("owner_user_id") is None]
        return {"items": store.list_sessions(visible, limit=20)}

    @app.post("/api/sessions")
    async def new_session(body: NewSession, owner=Depends(principal)):
        if not body.adult_confirmed:
            raise HTTPException(422, "Adult confirmation is required for this prototype.")
        if store.session_count(owner["id"] if owner else None) >= 100:
            raise HTTPException(422, "Session limit reached; remove older sessions first.")
        if body.memory_from_session_id:
            require(body.memory_from_session_id, owner)
        try:
            session = store.create(body.mode, body.character_id, body.memory_from_session_id, body.language,
                                   owner["id"] if owner else None)
            store.audit_event(actor(owner), "session_created", session["id"])
            return session_payload(session)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None

    @app.post("/api/data-agent")
    async def data_analysis(body: AnalysisInput, request: Request, owner=Depends(principal)):
        budgets.accept(actor(owner, request))
        try:
            async with budgets.slot():
                result = await asyncio.wait_for(asyncio.to_thread(analyze, body.question), timeout=settings.tool_timeout)
            store.audit_event(actor(owner, request), "synthetic_analysis", count=len(result.get("rows", [])))
            return result
        except ValueError:
            raise HTTPException(422, "Unsupported or unsafe analysis question; use synthetic demo topics only.") from None
        except TimeoutError:
            raise HTTPException(504, "Synthetic analysis timed out; no private data was accessed.") from None

    @app.get("/api/sessions/{sid}")
    async def read_session(sid: str, owner=Depends(principal)):
        return {**session_payload(require(sid, owner)), "messages": store.history(sid, 100), "memories": store.memories(sid), "insights": store.insights(sid)}

    @app.post("/api/sessions/{sid}/review-access")
    async def review_access(sid: str, body: ReviewAccessInput, owner=Depends(principal)):
        require(sid, owner)
        async with locked(sid):
            require(sid, owner)
            store.review_access(sid, body.allowed)
            store.audit_event(actor(owner), "review_access_changed", sid, allowed=body.allowed)
            return {"ok": True, "allowed": body.allowed}

    @app.post("/api/sessions/{sid}/chat")
    async def chat(sid: str, body: ChatInput, request: Request, owner=Depends(principal)):
        require(sid, owner)
        try:
            cached = store.cached(sid, body.request_id, body.message)
        except ValueError:
            raise HTTPException(409, "Request ID was already used for a different message") from None
        if cached:
            return cached
        budgets.accept(actor(owner, request))
        async with locked(sid):
            require(sid, owner)
            try:
                cached = store.cached(sid, body.request_id, body.message)
            except ValueError:
                raise HTTPException(409, "Request ID was already used for a different message") from None
            if cached:
                return cached
            text = body.message.strip()
            if not text:
                raise HTTPException(422, "Message must not be blank")
            try:
                async with budgets.slot():
                    result = await agent.run(sid, text, body.language)
            except AgentFailure as exc:
                store.audit_event(actor(owner, request), "run_failed", sid, provider=exc.provider,
                                  reason=exc.reason, duration_ms=exc.latency_ms)
                return JSONResponse(status_code=502, content={"detail": "Model could not complete the turn. No mock fallback or half-turn was saved.",
                    "failure_reason": exc.reason, "trace": exc.trace, "provider": exc.provider, "latency_ms": exc.latency_ms})
            except (ProviderError, TimeoutError):
                store.audit_event(actor(owner, request), "run_failed", sid, reason="provider_or_timeout")
                raise HTTPException(502, "Model could not complete the turn. No mock fallback or half-turn was saved.") from None
            saved = store.commit_turn(sid, body.request_id, text, result)
            usage = (saved.get("usage") or {}).get("total_tokens")
            store.audit_event(actor(owner, request), "run_completed", sid, provider=saved["provider"],
                              run_id=saved["run_id"], duration_ms=saved["latency_ms"],
                              total_tokens=usage if isinstance(usage, int) and usage >= 0 else None)
            return saved

    @app.post("/api/sessions/{sid}/memories")
    async def add_memory(sid: str, body: MemoryInput, owner=Depends(principal)):
        require(sid, owner)
        async with locked(sid):
            require(sid, owner)
            content = body.content.strip()
            if not content:
                raise HTTPException(422, "Memory must not be blank")
            if len(store.memories(sid)) >= 100:
                raise HTTPException(422, "Memory limit reached; remove older memories first.")
            try:
                mid = store.memory_add(sid, content)
                store.audit_event(actor(owner), "memory_added", sid)
                return {"id": mid, "status": "approved"}
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None

    @app.put("/api/sessions/{sid}/memories/{mid}")
    async def correct_memory(sid: str, mid: str, body: MemoryCorrectionInput, owner=Depends(principal)):
        require(sid, owner)
        async with locked(sid):
            require(sid, owner)
            if not body.content.strip():
                raise HTTPException(422, "Memory must not be blank")
            try:
                corrected = store.memory_correct(sid, mid, body.content, approve_pending=body.approve_pending)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            if not corrected:
                raise HTTPException(404, "Memory not found")
            store.audit_event(actor(owner), "memory_corrected", sid)
            return {"ok": True, "status": "approved"}

    @app.post("/api/sessions/{sid}/memories/{mid}/{action}")
    async def memory_action(sid: str, mid: str, action: Literal["approve", "delete"], owner=Depends(principal)):
        require(sid, owner)
        async with locked(sid):
            require(sid, owner)
            try:
                found = store.memory_action(sid, mid, action)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            if not found:
                raise HTTPException(404, "Memory not found")
            store.audit_event(actor(owner), "memory_" + action, sid)
            return {"ok": True}

    @app.delete("/api/sessions/{sid}/history")
    async def clear_history(sid: str, owner=Depends(principal)):
        require(sid, owner)
        async with locked(sid):
            require(sid, owner)
            store.clear_history(sid)
            store.audit_event(actor(owner), "history_deleted", sid)
            return {"ok": True, "approved_memories_retained": True}

    @app.delete("/api/sessions/{sid}")
    async def delete_session(sid: str, owner=Depends(principal)):
        require(sid, owner)
        async with locked(sid):
            require(sid, owner)
            store.delete(sid)
            # Already queued callers retain this mutex and recheck existence after acquiring it.
            # UUIDs are never reused; new requests cannot create a replacement for a deleted session.
            locks.pop(sid, None)
            store.audit_event(actor(owner), "session_deleted", sid)
            return {"ok": True, "shared_memories_retained_only_if_other_sessions_exist": True}

    dist = ROOT / "web" / "dist"
    if dist.exists():
        class AppStaticFiles(StaticFiles):
            async def get_response(self, path, scope):
                try:
                    return await super().get_response(path, scope)
                except StarletteHTTPException as exc:
                    if exc.status_code == 404 and path.rstrip("/") == "admin":
                        return await super().get_response("index.html", scope)
                    raise
        app.mount("/", AppStaticFiles(directory=dist, html=True), name="web")
    return app


app = create_app()
