"""Central configuration. All secrets come from environment variables / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    telem_api_key: str = os.getenv("TELEM_API_KEY", "")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    telem_base: str = os.getenv("TELEM_BASE_URL", "https://router.telem.ai")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    vault_dir: Path = Path(os.getenv("RECALL_VAULT_DIR", str(ROOT / "vault")))
    host: str = os.getenv("RECALL_HOST", "127.0.0.1")
    port: int = int(os.getenv("RECALL_PORT", "8000"))
    frontend_origins: tuple[str, ...] = tuple(
        o.strip()
        for o in os.getenv(
            "RECALL_FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if o.strip()
    )

    native: bool = _bool("RECALL_NATIVE", False)
    native_key: str = os.getenv("RECALL_NATIVE_KEY", "")
    cdp_port: int = int(os.getenv("RECALL_CDP_PORT", "9338"))
    viewport_w: int = 1280
    viewport_h: int = 800
    headless: bool = _bool("RECALL_HEADLESS", True)
    dpr: float = float(os.getenv("RECALL_DPR", "1.5"))  # render scale of the remote page, for crisp text

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def key_status(self) -> dict[str, bool]:
        return {
            "telem": bool(self.telem_api_key),
            "tavily": bool(self.tavily_api_key),
            "openai": bool(self.openai_api_key),
            "anthropic": bool(self.anthropic_api_key),
        }


settings = Settings()
