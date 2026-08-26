from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from .models import FetchResult, Video
from .wbi import extract_key, sign_params

API_BASE = "https://api.bilibili.com"
NAV_PATH = "/x/web-interface/nav"
ARC_SEARCH_PATH = "/x/space/wbi/arc/search"
ARC_SEARCH_FALLBACK_PATH = "/x/space/arc/search"
DETAIL_PATH = "/x/web-interface/view"
MAX_DETAIL_LIMIT = 5

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://www.bilibili.com",
}

SPACE_HEADERS = {
    "User-Agent": DEFAULT_HEADERS["User-Agent"],
    "Referer": "https://space.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}


class BilibiliFetchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_type: str = "fetch_error",
        attempts: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.attempts = attempts or []


class BilibiliClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        cookie: str = "",
        user_agent: str | None = None,
        rate_limit_delay_seconds: float = 2.0,
        before_request: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.http = http_client
        self.cookie = cookie
        self.user_agent = user_agent or DEFAULT_HEADERS["User-Agent"]
        self.rate_limit_delay_seconds = rate_limit_delay_seconds
        self.before_request = before_request
        self._wbi_keys: tuple[str, str] | None = None

    async def fetch_user_videos(
        self,
        uid: str,
        *,
        limit: int = 10,
        detail_limit: int = 0,
    ) -> FetchResult:
        uid = _validate_uid(uid)
        detail_limit = min(max(int(detail_limit), 0), MAX_DETAIL_LIMIT)
        fetched_at = datetime.now(UTC)
        attempts: list[dict[str, object]] = []

        try:
            response = await self._get_json(
                ARC_SEARCH_FALLBACK_PATH,
                params=_search_params(uid, limit),
                referer=f"https://space.bilibili.com/{uid}/video",
                headers=SPACE_HEADERS,
            )
            attempts.append(
                {
                    "fetcher": "official_legacy",
                    "path": ARC_SEARCH_FALLBACK_PATH,
                    "code": response.get("code", 0),
                }
            )
            payload = _require_success(response, source="official_legacy")
            result = _build_result(uid, payload, "official_legacy", attempts, fetched_at, limit)
            return await self._enrich_details(result, detail_limit=detail_limit)
        except Exception as exc:  # noqa: BLE001 - any upstream failure should try WBI.
            attempts.append(_attempt_error("official_legacy", ARC_SEARCH_FALLBACK_PATH, exc))

        if _needs_rate_limit_pause(attempts[-1]):
            await asyncio.sleep(self.rate_limit_delay_seconds)

        try:
            img_key, sub_key = await self._get_wbi_keys()
            response = await self._get_json(
                ARC_SEARCH_PATH,
                params=sign_params(_search_params(uid, limit), img_key, sub_key),
                referer=f"https://space.bilibili.com/{uid}/video",
                headers=SPACE_HEADERS,
            )
            attempts.append(
                {
                    "fetcher": "official_wbi",
                    "path": ARC_SEARCH_PATH,
                    "code": response.get("code", 0),
                }
            )
            payload = _require_success(response, source="official_wbi")
            result = _build_result(uid, payload, "official_wbi", attempts, fetched_at, limit)
            return await self._enrich_details(result, detail_limit=detail_limit)
        except Exception as exc:
            attempts.append(_attempt_error("official_wbi", ARC_SEARCH_PATH, exc))
            raise BilibiliFetchError(
                f"unable to fetch public videos for uid {uid}: {_safe_error(attempts[-1])}",
                error_type=_classify_failure(attempts),
                attempts=attempts,
            ) from exc

    async def _get_wbi_keys(self) -> tuple[str, str]:
        if self._wbi_keys:
            return self._wbi_keys
        response = await self._get_json(
            NAV_PATH, referer="https://www.bilibili.com/", headers=DEFAULT_HEADERS
        )
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        data = data.get("wbi_img") if isinstance(data.get("wbi_img"), dict) else {}
        img_url = str(data.get("img_url") or "")
        sub_url = str(data.get("sub_url") or "")
        if not img_url or not sub_url:
            raise BilibiliFetchError(
                "Bilibili nav response did not include WBI keys", error_type="protocol"
            )
        self._wbi_keys = (extract_key(img_url), extract_key(sub_url))
        return self._wbi_keys

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, object] | None = None,
        referer: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if self.before_request is not None:
            await self.before_request()
        request_headers = dict(headers or {})
        request_headers["User-Agent"] = self.user_agent
        request_headers.setdefault("Referer", referer)
        if self.cookie:
            request_headers["Cookie"] = self.cookie
        response = await self.http.get(f"{API_BASE}{path}", params=params, headers=request_headers)
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise BilibiliFetchError(
                "Bilibili returned non-JSON response", error_type="invalid_response"
            ) from exc
        if not isinstance(payload, dict):
            raise BilibiliFetchError(
                "Bilibili returned an unexpected JSON shape", error_type="invalid_response"
            )
        payload.setdefault("_http_status", response.status_code)
        return payload

    async def verify_cookie(self) -> dict[str, object]:
        if not self.cookie:
            return {"configured": False, "valid": False, "reason": "Cookie 未配置"}
        try:
            response = await self._get_json(
                NAV_PATH, referer="https://www.bilibili.com/", headers=DEFAULT_HEADERS
            )
        except Exception as exc:  # noqa: BLE001 - verification must return a safe result.
            return {"configured": True, "valid": False, "reason": str(exc)[:300]}
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        if response.get("code") == 0 and data.get("isLogin"):
            level_info = data.get("level_info") if isinstance(data.get("level_info"), dict) else {}
            return {
                "configured": True,
                "valid": True,
                "nickname": str(data.get("uname") or ""),
                "mid": int(data.get("mid") or 0),
                "level": int(level_info.get("current_level") or 0),
            }
        return {
            "configured": True,
            "valid": False,
            "reason": str(response.get("message") or "Cookie 无效或未登录"),
        }

    async def _enrich_details(
        self,
        result: FetchResult,
        *,
        detail_limit: int,
    ) -> FetchResult:
        if detail_limit <= 0 or not result.videos:
            return result
        selected = sorted(
            result.videos,
            key=lambda video: (
                -(video.view_count or 0),
                -(video.comment_count or 0),
                -(video.published_at.timestamp() if video.published_at else 0),
                video.bvid,
            ),
        )[:detail_limit]
        by_bvid = {video.bvid: video for video in result.videos}
        for video in selected:
            try:
                payload = await self._get_json(
                    DETAIL_PATH,
                    params={"bvid": video.bvid},
                    referer=video.url,
                    headers=DEFAULT_HEADERS,
                )
                data = _require_success(payload, source="official_detail")
                stat = data.get("stat") if isinstance(data.get("stat"), dict) else {}
                by_bvid[video.bvid] = video.model_copy(
                    update={
                        "view_count": _prefer_int(stat.get("view"), video.view_count),
                        "danmaku_count": _int_or_none(stat.get("danmaku")),
                        "comment_count": _prefer_int(stat.get("reply"), video.comment_count),
                        "like_count": _int_or_none(stat.get("like")),
                        "coin_count": _int_or_none(stat.get("coin")),
                        "favorite_count": _int_or_none(stat.get("favorite")),
                        "share_count": _int_or_none(stat.get("share")),
                    }
                )
                result.attempts.append(
                    {"fetcher": "official_detail", "bvid": video.bvid, "status": "success"}
                )
            except Exception as exc:  # noqa: BLE001 - optional enrichment must not drop the list.
                result.attempts.append(
                    {
                        "fetcher": "official_detail",
                        "bvid": video.bvid,
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:300],
                    }
                )
        result.videos = [by_bvid[video.bvid] for video in result.videos]
        return result


def _search_params(uid: str, limit: int) -> dict[str, object]:
    return {
        "mid": uid,
        "ps": min(max(limit, 1), 50),
        "tid": 0,
        "pn": 1,
        "keyword": "",
        "order": "pubdate",
        "platform": "web",
        "web_location": 1550101,
        "order_avoided": "true",
    }


def _require_success(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    code = payload.get("code", 0)
    if code != 0:
        message = str(payload.get("message") or payload.get("msg") or "unknown error")
        raise BilibiliFetchError(
            f"{source} returned business code {code}: {message}", error_type="business_error"
        )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BilibiliFetchError(
            f"{source} response has no data object", error_type="invalid_response"
        )
    return data


def _build_result(
    uid: str,
    data: dict[str, Any],
    fetcher: str,
    attempts: list[dict[str, object]],
    fetched_at: datetime,
    limit: int,
) -> FetchResult:
    listing = data.get("list") if isinstance(data.get("list"), dict) else {}
    rows = listing.get("vlist") if isinstance(listing.get("vlist"), list) else []
    videos = [_video_from_row(row) for row in rows[:limit] if isinstance(row, dict)]
    first_row = rows[0] if rows and isinstance(rows[0], dict) else {}
    owner = data.get("owner") if isinstance(data.get("owner"), dict) else {}
    return FetchResult(
        uid=uid,
        name=str(owner.get("name") or data.get("name") or first_row.get("author") or uid),
        face=str(owner.get("face") or data.get("face") or ""),
        videos=videos,
        fetcher=fetcher,
        attempts=attempts,
        fetched_at=fetched_at,
    )


def _video_from_row(row: dict[str, Any]) -> Video:
    bvid = str(row.get("bvid") or "")
    aid = _int_or_none(row.get("aid"))
    if not bvid and aid is None:
        raise BilibiliFetchError(
            "video row has neither bvid nor aid", error_type="invalid_response"
        )
    video_id = bvid or f"av{aid}"
    return Video(
        bvid=bvid or video_id,
        aid=aid,
        title=_clean(row.get("title")),
        description=_clean(row.get("description")),
        url=f"https://www.bilibili.com/video/{video_id}",
        published_at=_unix_datetime(row.get("created")),
        thumbnail_url=_clean(row.get("pic")),
        duration_seconds=_duration_seconds(row.get("length")),
        view_count=_int_or_none(row.get("play")),
        comment_count=_int_or_none(row.get("comment")),
        # These fields are not guaranteed by the space listing endpoint. Keep
        # them nullable so downstream consumers can distinguish unavailable
        # metrics from a measured zero without scraping rendered page chrome.
        danmaku_count=_int_or_none(row.get("video_review")),
        like_count=_int_or_none(row.get("like")),
        coin_count=_int_or_none(row.get("coin")),
        favorite_count=_int_or_none(row.get("favorites")),
        share_count=_int_or_none(row.get("share")),
    )


def _attempt_error(fetcher: str, path: str, exc: Exception) -> dict[str, object]:
    if isinstance(exc, BilibiliFetchError):
        return {
            "fetcher": fetcher,
            "path": path,
            "error_type": exc.error_type,
            "error": str(exc)[:500],
        }
    return {
        "fetcher": fetcher,
        "path": path,
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
    }


def _needs_rate_limit_pause(attempt: dict[str, object]) -> bool:
    error = str(attempt.get("error") or "")
    return any(marker in error for marker in ("-799", "412", "频繁", "Precondition"))


def _safe_error(attempt: dict[str, object]) -> str:
    return str(attempt.get("error") or attempt.get("error_type") or "unknown error")


def _classify_failure(attempts: list[dict[str, object]]) -> str:
    error_types = {str(item.get("error_type")) for item in attempts if item.get("error_type")}
    if "invalid_input" in error_types:
        return "invalid_input"
    if "business_error" in error_types or "HTTPStatusError" in error_types:
        return "blocked_or_unavailable"
    if "protocol" in error_types or "invalid_response" in error_types:
        return "protocol"
    return "fetch_error"


def _validate_uid(value: str) -> str:
    uid = str(value).strip()
    if not re.fullmatch(r"\d{1,20}", uid):
        raise BilibiliFetchError("uid must contain 1-20 digits", error_type="invalid_input")
    return uid


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _prefer_int(value: Any, fallback: int | None) -> int | None:
    parsed = _int_or_none(value)
    return fallback if parsed is None else parsed


def _unix_datetime(value: Any) -> datetime | None:
    timestamp = _int_or_none(value)
    return datetime.fromtimestamp(timestamp, tz=UTC) if timestamp else None


def _duration_seconds(value: Any) -> int | None:
    match = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", str(value or "").strip())
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
