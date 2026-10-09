import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    provider: str = "mock"
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    timeout: float = 30
    max_steps: int = 4
    max_output_tokens: int = 1200
    tool_timeout: float = 3
    db_path: str = "data/harbor.sqlite3"
    allowed_origins: tuple[str, ...] = ()
    allowed_hosts: tuple[str, ...] = ()
    client_token: str = ""
    admin_token_minutes: int = 60
    auth_mode: str = "local_demo"
    registration_enabled: bool = False
    user_token_minutes: int = 60
    chat_requests_per_minute: int = 20
    max_concurrent_runs: int = 4
    run_queue_timeout: float = 2
    audit_retention_days: int = 30

    @classmethod
    def from_env(cls):
        return cls(
            provider=os.getenv("HARBOR_PROVIDER", "mock"),
            api_base=os.getenv("HARBOR_API_BASE", "").rstrip("/"),
            api_key=os.getenv("HARBOR_API_KEY", ""),
            model=os.getenv("HARBOR_MODEL", ""),
            timeout=float(os.getenv("HARBOR_TIMEOUT_SECONDS", "30")),
            max_steps=max(1, min(8, int(os.getenv("HARBOR_MAX_STEPS", "4")))),
            max_output_tokens=max(600, min(2000, int(os.getenv("HARBOR_MAX_OUTPUT_TOKENS", "1200")))),
            tool_timeout=max(0.05, min(10, float(os.getenv("HARBOR_TOOL_TIMEOUT_SECONDS", "3")))),
            db_path=os.getenv("HARBOR_DB", str(ROOT / "data" / "harbor.sqlite3")),
            allowed_origins=tuple(x.strip() for x in os.getenv("HARBOR_ALLOWED_ORIGINS", "").split(",") if x.strip()),
            allowed_hosts=tuple(x.strip().lower() for x in os.getenv("HARBOR_ALLOWED_HOSTS", "").split(",") if x.strip()),
            client_token=os.getenv("HARBOR_CLIENT_TOKEN", ""),
            admin_token_minutes=max(5, min(120, int(os.getenv("HARBOR_ADMIN_TOKEN_MINUTES", "60")))),
            auth_mode=os.getenv("HARBOR_AUTH_MODE", "local_demo"),
            registration_enabled=os.getenv("HARBOR_REGISTRATION_ENABLED", "false").lower() == "true",
            user_token_minutes=max(5, min(1440, int(os.getenv("HARBOR_USER_TOKEN_MINUTES", "60")))),
            chat_requests_per_minute=max(1, min(120, int(os.getenv("HARBOR_CHAT_REQUESTS_PER_MINUTE", "20")))),
            max_concurrent_runs=max(1, min(16, int(os.getenv("HARBOR_MAX_CONCURRENT_RUNS", "4")))),
            run_queue_timeout=max(0.01, min(10, float(os.getenv("HARBOR_RUN_QUEUE_TIMEOUT_SECONDS", "2")))),
            audit_retention_days=max(1, min(90, int(os.getenv("HARBOR_AUDIT_RETENTION_DAYS", "30")))),
        )
