from __future__ import annotations

from datetime import UTC
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring

from .models import FetchResult


def render_rss(result: FetchResult, *, self_url: str | None = None) -> bytes:
    register_namespace("media", "http://search.yahoo.com/mrss/")
    register_namespace("atom", "http://www.w3.org/2005/Atom")
    register_namespace("dc", "http://purl.org/dc/elements/1.1/")
    register_namespace("bili", "urn:bilibili-rss:metrics")
    root = Element("rss", {"version": "2.0"})
    channel = SubElement(root, "channel")
    feed_url = self_url or f"/rss/{result.uid}"
    _text(channel, "title", f"{result.name} 的 Bilibili 视频")
    _text(channel, "link", f"https://space.bilibili.com/{result.uid}/video")
    _text(channel, "description", f"Bilibili UP 主 {result.name} 的公开视频订阅")
    _text(channel, "language", "zh-CN")
    _text(channel, "generator", "bilibili-rss-service")
    _text(channel, "ttl", "5")
    if result.face:
        image = SubElement(channel, "image")
        _text(image, "url", _https_url(result.face))
        _text(image, "title", result.name)
        _text(image, "link", f"https://space.bilibili.com/{result.uid}/video")
    if result.fetched_at:
        _text(channel, "lastBuildDate", _format_date(result.fetched_at))
    SubElement(
        channel,
        "{http://www.w3.org/2005/Atom}link",
        {"href": feed_url, "rel": "self", "type": "application/rss+xml"},
    )
    for video in result.videos:
        item = SubElement(channel, "item")
        _text(item, "title", video.title or video.bvid)
        _text(item, "link", video.url)
        _text(item, "guid", video.url)
        _text(item, "description", video.description)
        _text(item, "{http://purl.org/dc/elements/1.1/}creator", result.name)
        if video.published_at:
            _text(
                item,
                "pubDate",
                video.published_at.astimezone(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            )
        if video.thumbnail_url:
            SubElement(
                item,
                "{http://search.yahoo.com/mrss/}thumbnail",
                {"url": _https_url(video.thumbnail_url)},
            )
        metrics = (
            ("viewCount", video.view_count),
            ("danmakuCount", video.danmaku_count),
            ("commentCount", video.comment_count),
            ("likeCount", video.like_count),
            ("coinCount", video.coin_count),
            ("favoriteCount", video.favorite_count),
            ("shareCount", video.share_count),
        )
        for name, value in metrics:
            if value is not None:
                _text(item, f"{{urn:bilibili-rss:metrics}}{name}", str(value))
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<?xml-stylesheet type="text/xsl" href="/static/rss.xsl"?>\n'
        + tostring(root, encoding="utf-8")
    )


def _format_date(value) -> str:
    return value.astimezone(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _https_url(value: str) -> str:
    return f"https:{value}" if value.startswith("//") else value


def _text(parent: Element, name: str, value: str) -> None:
    node = SubElement(parent, name)
    node.text = value
