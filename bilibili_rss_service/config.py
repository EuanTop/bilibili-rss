from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    timeout_seconds: float = 20.0
    cache_ttl_seconds: int = 300
    max_items: int = 10
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
    cookie: str = ""
    cookie_file: Path = Path("data/bilibili.cookie")
    rate_limit_delay_seconds: float = 2.0
    max_concurrency: int = 4
    upstream_min_interval_seconds: float = 0.5
    data_dir: Path = Path("data")
    audit_max_bytes: int = 5 * 1024 * 1024
    audit_backup_count: int = 3

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> Settings:
        load_dotenv(env_file, override=False)
        cookie_file = Path(os.getenv("BILIBILI_COOKIE_FILE", "data/bilibili.cookie")).expanduser()
        cookie = ""
        if cookie_file.is_file():
            cookie = cookie_file.read_text(encoding="utf-8").strip()
        return cls(
            host=os.getenv("BILIBILI_RSS_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_int_env("BILIBILI_RSS_PORT", 8765, minimum=1, maximum=65535),
            timeout_seconds=_float_env("BILIBILI_TIMEOUT_SECONDS", 20.0, minimum=1.0),
            cache_ttl_seconds=_int_env("BILIBILI_CACHE_TTL_SECONDS", 300, minimum=0),
            max_items=_int_env("BILIBILI_MAX_ITEMS", 10, minimum=1, maximum=50),
            user_agent=os.getenv("BILIBILI_USER_AGENT", cls.user_agent).strip() or cls.user_agent,
            cookie=cookie,
            cookie_file=cookie_file,
            rate_limit_delay_seconds=_float_env(
                "BILIBILI_RATE_LIMIT_DELAY_SECONDS", 2.0, minimum=0.5
            ),
            max_concurrency=_int_env("BILIBILI_MAX_CONCURRENCY", 4, minimum=1, maximum=8),
            upstream_min_interval_seconds=_float_env(
                "BILIBILI_UPSTREAM_MIN_INTERVAL_SECONDS", 0.5, minimum=0.1
            ),
            data_dir=Path(os.getenv("BILIBILI_DATA_DIR", "data")).expanduser(),
            audit_max_bytes=_int_env(
                "BILIBILI_AUDIT_MAX_BYTES",
                5 * 1024 * 1024,
                minimum=1024,
            ),
            audit_backup_count=_int_env(
                "BILIBILI_AUDIT_BACKUP_COUNT",
                3,
                minimum=1,
                maximum=10,
            ),
        )


def _int_env(name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    if value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


def _float_env(name: str, default: float, *, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)
