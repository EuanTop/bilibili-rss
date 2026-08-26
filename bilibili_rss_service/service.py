from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from .client import BilibiliClient, BilibiliFetchError
from .config import Settings
from .models import FetchResult


class BilibiliService:
    def __init__(
        self, settings: Settings | None = None, *, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings or Settings.from_env()
        self._external_http = http_client
        self._http: httpx.AsyncClient | None = http_client
        self._bilibili_client: BilibiliClient | None = None
        self._cache: dict[str, tuple[float, FetchResult, int]] = {}
        self._uid_locks: dict[str, asyncio.Lock] = {}
        self._concurrency = asyncio.Semaphore(self.settings.max_concurrency)
        self._upstream_lock = asyncio.Lock()
        self._next_upstream_at = 0.0
        self._audit_lock = asyncio.Lock()

    async def fetch(self, uid: str, *, force: bool = False, detail_limit: int = 0) -> FetchResult:
        detail_limit = min(max(int(detail_limit), 0), 5)
        now = asyncio.get_running_loop().time()
        cached = self._cache.get(uid)
        if (
            not force
            and cached
            and now - cached[0] < self.settings.cache_ttl_seconds
            and cached[2] >= detail_limit
        ):
            return cached[1]
        uid_lock = self._uid_locks.setdefault(uid, asyncio.Lock())
        async with uid_lock:
            now = asyncio.get_running_loop().time()
            cached = self._cache.get(uid)
            if (
                not force
                and cached
                and now - cached[0] < self.settings.cache_ttl_seconds
                and cached[2] >= detail_limit
            ):
                return cached[1]
            async with self._concurrency:
                client = await self._get_bilibili_client()
                try:
                    result = await client.fetch_user_videos(
                        uid,
                        limit=self.settings.max_items,
                        detail_limit=detail_limit,
                    )
                except BilibiliFetchError as exc:
                    await self._write_audit(
                        {
                            "uid": uid,
                            "status": "failed",
                            "error_type": exc.error_type,
                            "error": str(exc),
                            "attempts": exc.attempts,
                            "fetched_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    raise
                self._cache[uid] = (asyncio.get_running_loop().time(), result, detail_limit)
                await self._write_audit(
                    {
                        "uid": uid,
                        "status": "success" if result.videos else "empty",
                        "fetcher": result.fetcher,
                        "video_count": len(result.videos),
                        "attempts": result.attempts,
                        "fetched_at": result.fetched_at.isoformat(),
                    }
                )
                return result

    async def _get_bilibili_client(self) -> BilibiliClient:
        client = self._bilibili_client
        if client is None:
            client = BilibiliClient(
                await self._client(),
                cookie=self.settings.cookie,
                user_agent=self.settings.user_agent,
                rate_limit_delay_seconds=self.settings.rate_limit_delay_seconds,
                before_request=self._before_upstream_request,
            )
            self._bilibili_client = client
        return client

    async def _before_upstream_request(self) -> None:
        async with self._upstream_lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            wait_for = self._next_upstream_at - now
            if wait_for > 0:
                await asyncio.sleep(wait_for)
                now = loop.time()
            self._next_upstream_at = (
                max(now, self._next_upstream_at) + self.settings.upstream_min_interval_seconds
            )

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=self.settings.timeout_seconds,
                follow_redirects=True,
                trust_env=False,
                headers={"User-Agent": self.settings.user_agent},
            )
        return self._http

    async def close(self) -> None:
        if self._http is not None and self._external_http is None:
            await self._http.aclose()
            self._http = None
        self._bilibili_client = None

    async def verify_cookie(self) -> dict[str, object]:
        client = await self._get_bilibili_client()
        return await client.verify_cookie()

    async def _write_audit(self, record: dict[str, object]) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        async with self._audit_lock:
            path = self.settings.data_dir / "attempts.jsonl"
            self._rotate_audit(path)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    def _rotate_audit(self, path: Path) -> None:
        try:
            if path.stat().st_size < self.settings.audit_max_bytes:
                return
        except FileNotFoundError:
            return
        path.with_name(f"{path.name}.{self.settings.audit_backup_count}").unlink(missing_ok=True)
        for index in range(self.settings.audit_backup_count - 1, 0, -1):
            source = path.with_name(f"{path.name}.{index}")
            if source.exists():
                source.replace(path.with_name(f"{path.name}.{index + 1}"))
        path.replace(path.with_name(f"{path.name}.1"))
