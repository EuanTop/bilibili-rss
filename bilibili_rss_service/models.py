from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Video(BaseModel):
    bvid: str
    aid: int | None = None
    title: str
    description: str = ""
    url: str
    published_at: datetime | None = None
    thumbnail_url: str = ""
    duration_seconds: int | None = None
    view_count: int | None = None
    comment_count: int | None = None
    danmaku_count: int | None = None
    like_count: int | None = None
    coin_count: int | None = None
    favorite_count: int | None = None
    share_count: int | None = None


class FetchResult(BaseModel):
    uid: str
    name: str
    face: str = ""
    videos: list[Video] = Field(default_factory=list)
    fetcher: str
    attempts: list[dict[str, object]] = Field(default_factory=list)
    fetched_at: datetime
