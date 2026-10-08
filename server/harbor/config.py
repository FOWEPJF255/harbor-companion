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
    db_path: str = "data/harbor.sqlite3"

    @classmethod
    def from_env(cls):
        return cls(
            provider=os.getenv("HARBOR_PROVIDER", "mock"),
            api_base=os.getenv("HARBOR_API_BASE", "").rstrip("/"),
            api_key=os.getenv("HARBOR_API_KEY", ""),
            model=os.getenv("HARBOR_MODEL", ""),
            timeout=float(os.getenv("HARBOR_TIMEOUT_SECONDS", "30")),
            max_steps=max(1, min(8, int(os.getenv("HARBOR_MAX_STEPS", "4")))),
            db_path=os.getenv("HARBOR_DB", str(ROOT / "data" / "harbor.sqlite3")),
        )
