"""User authentication for account mode, separate from the management plane."""
from collections import deque
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from threading import RLock
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, field_validator

PASSWORD_ITERATIONS = 600_000
MAX_BODY_BYTES = 4096
MAX_LOGIN_ATTEMPTS = 10
ATTEMPT_WINDOW_SECONDS = 60
MAX_RATE_LIMIT_KEYS = 4096
USER_TOKEN_PATTERN = re.compile(r"^usr_[A-Za-z0-9_-]{43}$")
NO_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
USER_BEARER = HTTPBearer(auto_error=False, scheme_name="UserBearer")


def authentication_error(status, message):
    headers = dict(NO_CACHE)
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return HTTPException(status, message, headers=headers)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PASSWORD_ITERATIONS).hex()


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128, repr=False, json_schema_extra={"format": "password"})

    @field_validator("username", mode="before")
    @classmethod
    def normalized_username(cls, value):
        if not isinstance(value, str) or not value.isascii():
            raise ValueError("Invalid username")
        return value.strip().lower()


class Registration(Credentials):
    adult_confirmed: StrictBool


async def request_input(request, model):
    """Parse a bounded JSON body without returning validation inputs or passwords."""
    data = bytearray()
    try:
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BODY_BYTES:
                raise authentication_error(422, "Invalid authentication input.")
            data.extend(chunk)
        payload = json.loads(data.decode("utf-8"))
        return model.model_validate(payload)
    except (ValueError, UnicodeError, ValidationError):
        raise authentication_error(422, "Invalid authentication input.") from None


class UserAuth:
    """Opaque, database-checked credentials with explicit expiry and revocation."""

    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.ttl = max(60, min(86_400, int(settings.user_token_minutes) * 60))
        self._attempts = {}
        self._attempt_lock = RLock()
        with store.connect() as db:
            self.ensure_schema(db)

    @staticmethod
    def ensure_schema(db):
        # Store calls this before creating owner foreign keys; no Store import is needed.
        db.execute("""CREATE TABLE IF NOT EXISTS users(
            id TEXT NOT NULL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            adult_confirmed INTEGER NOT NULL CHECK(adult_confirmed IN (0,1)),
            created TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS user_tokens(
            token_hash TEXT NOT NULL PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL,
            created TEXT NOT NULL,
            revoked_at INTEGER)""")
        db.execute("CREATE INDEX IF NOT EXISTS user_tokens_owner_expiry ON user_tokens(user_id,expires_at)")

    @staticmethod
    def public_user(row):
        return {"id": row["id"], "username": row["username"]}

    def rate_limit(self, request):
        # Forwarded headers are untrusted. The socket peer is the only IP key here.
        peer = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._attempt_lock:
            expired = [key for key, queue in self._attempts.items() if not queue or queue[-1] <= now - ATTEMPT_WINDOW_SECONDS]
            for key in expired:
                self._attempts.pop(key, None)
            if peer not in self._attempts and len(self._attempts) >= MAX_RATE_LIMIT_KEYS:
                raise authentication_error(429, "Too many authentication attempts; try again later.")
            queue = self._attempts.setdefault(peer, deque())
            while queue and queue[0] <= now - ATTEMPT_WINDOW_SECONDS:
                queue.popleft()
            if len(queue) >= MAX_LOGIN_ATTEMPTS:
                raise authentication_error(429, "Too many authentication attempts; try again later.")
            queue.append(now)

    async def provision(self, username, password, adult_confirmed=True):
        """Create a user only from a trusted admin/CLI or gated registration path."""
        try:
            credentials = Credentials.model_validate({"username": username, "password": password})
        except ValidationError:
            raise ValueError("Invalid user account input.") from None
        if adult_confirmed is not True:
            raise ValueError("Adult confirmation is required.")
        salt = secrets.token_hex(16)
        digest = await run_in_threadpool(password_digest, credentials.password, salt)
        user_id = secrets.token_hex(16)
        try:
            with self.store.connect() as db:
                db.execute("INSERT INTO users(id,username,password_hash,salt,active,adult_confirmed,created) VALUES(?,?,?,?,1,1,?)",
                           (user_id, credentials.username, digest, salt, timestamp()))
        except sqlite3.IntegrityError:
            raise ValueError("Unable to create an account using these details.") from None
        return {"id": user_id, "username": credentials.username}

    async def login(self, credentials):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (credentials.username,)).fetchone()
        # Unknown accounts pay the same password-hashing cost and use the same error.
        digest = await run_in_threadpool(password_digest, credentials.password, row["salt"] if row else "00" * 16)
        expected = row["password_hash"] if row else "00" * 32
        password_matches = hmac.compare_digest(digest, expected)
        if not row or not password_matches or not row["active"]:
            raise authentication_error(401, "Invalid user credentials.")
        return self.issue(self.public_user(row))

    def issue(self, user):
        expiry = int(time.time()) + self.ttl
        for _ in range(3):
            token = "usr_" + secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode("ascii")).hexdigest()
            try:
                with self.store.connect() as db:
                    current = db.execute("SELECT id,username,active FROM users WHERE id=?", (user["id"],)).fetchone()
                    if not current or not current["active"]:
                        raise authentication_error(401, "Invalid user credentials.")
                    db.execute("INSERT INTO user_tokens VALUES(?,?,?,?,NULL)", (digest, user["id"], expiry, timestamp()))
                return {"access_token": token, "expires_in": self.ttl, "user": self.public_user(current)}
            except sqlite3.IntegrityError:
                continue
        raise authentication_error(503, "Authentication is temporarily unavailable.")

    async def require(self, request: Request, _credentials=Depends(USER_BEARER)):
        value = request.headers.get("authorization", "")
        scheme, separator, token = value.partition(" ")
        if not separator or scheme.lower() != "bearer" or not USER_TOKEN_PATTERN.fullmatch(token):
            raise authentication_error(401, "User login required.")
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        with self.store.connect() as db:
            row = db.execute("""SELECT u.id,u.username,u.active,t.expires_at,t.revoked_at
                FROM user_tokens t JOIN users u ON t.user_id=u.id WHERE t.token_hash=?""", (digest,)).fetchone()
        if not row or not row["active"] or row["revoked_at"] is not None or row["expires_at"] <= time.time():
            raise authentication_error(401, "User login required.")
        request.state.harbor_user_token_hash = digest
        request.state.harbor_user_token_expiry = row["expires_at"]
        return self.public_user(row)

    def revoke_current(self, request, user):
        with self.store.connect() as db:
            db.execute("UPDATE user_tokens SET revoked_at=? WHERE token_hash=? AND user_id=?",
                       (int(time.time()), request.state.harbor_user_token_hash, user["id"]))

    def revoke_user(self, user_id):
        """Trusted account lifecycle operations may revoke every existing login."""
        with self.store.connect() as db:
            db.execute("UPDATE user_tokens SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (int(time.time()), user_id))


def user_router(auth):
    router = APIRouter(prefix="/api/auth", tags=["user accounts"])

    def input_schema(model):
        return {"requestBody": {"required": True, "content": {"application/json": {"schema": model.model_json_schema()}}}}

    @router.post("/register", openapi_extra=input_schema(Registration))
    async def register(request: Request):
        auth.rate_limit(request)
        if not auth.settings.registration_enabled or getattr(auth.settings, "auth_mode", "accounts") != "accounts":
            raise authentication_error(403, "Public registration is disabled.")
        body = await request_input(request, Registration)
        if not body.adult_confirmed:
            raise authentication_error(422, "Adult confirmation is required.")
        try:
            user = await auth.provision(body.username, body.password, body.adult_confirmed)
        except ValueError:
            raise authentication_error(400, "Unable to register using these details.") from None
        return JSONResponse(auth.issue(user), headers=NO_CACHE)

    @router.post("/login", openapi_extra=input_schema(Credentials))
    async def login(request: Request):
        auth.rate_limit(request)
        body = await request_input(request, Credentials)
        return JSONResponse(await auth.login(body), headers=NO_CACHE)

    @router.get("/me")
    async def me(request: Request, user=Depends(auth.require)):
        return JSONResponse({"user": user, "expires_in": max(0, int(request.state.harbor_user_token_expiry - time.time()))}, headers=NO_CACHE)

    @router.post("/logout")
    async def logout(request: Request, user=Depends(auth.require)):
        auth.revoke_current(request, user)
        return JSONResponse({"ok": True}, headers=NO_CACHE)

    return router
