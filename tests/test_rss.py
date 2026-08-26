from datetime import UTC, datetime
from xml.etree.ElementTree import fromstring

from bilibili_rss_service.models import FetchResult, Video
from bilibili_rss_service.rss import render_rss


def test_render_rss_escapes_xml_and_includes_items() -> None:
    payload = render_rss(
        FetchResult(
            uid="1",
            name="测试 & UP",
            face="//i0.hdslb.com/face.jpg",
            videos=[
                Video(
                    bvid="BV1",
                    title="A < B",
                    description="hello & world",
                    url="https://www.bilibili.com/video/BV1",
                    thumbnail_url="//i0.hdslb.com/cover.jpg",
                    published_at=datetime(2026, 1, 1, tzinfo=UTC),
                    view_count=1234567,
                    danmaku_count=2345,
                    comment_count=345,
                    like_count=45678,
                    coin_count=5678,
                    favorite_count=6789,
                    share_count=789,
                )
            ],
            fetcher="test",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    text = payload.decode()
    root = fromstring(text.split("?>\n", 2)[-1])
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    assert "A &lt; B" in text
    assert "hello &amp; world" in text
    assert "xml-stylesheet" in text
    assert "lastBuildDate" in text
    assert "atom:link" in text
    assert "https://i0.hdslb.com/face.jpg" in text
    assert "https://i0.hdslb.com/cover.jpg" in text
    assert "bili:viewCount>1234567" in text
    assert "bili:likeCount>45678" in text
    assert "bili:shareCount>789" in text
    assert "<item>" in text
