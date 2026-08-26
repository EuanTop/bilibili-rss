import httpx
import pytest

from bilibili_rss_service.client import BilibiliClient, BilibiliFetchError


@pytest.mark.asyncio
async def test_public_legacy_endpoint_is_preferred() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/x/space/arc/search")
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "list": {
                        "vlist": [
                            {
                                "bvid": "BVTEST",
                                "aid": 1,
                                "title": "公开视频",
                                "description": "简介",
                                "author": "UP",
                                "created": 1700000000,
                                "length": "01:02",
                                "play": 1234,
                                "comment": 9,
                                "video_review": 17,
                                "like": 31,
                                "coin": 7,
                                "favorites": 11,
                                "share": 4,
                            }
                        ]
                    }
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await BilibiliClient(http).fetch_user_videos("1", limit=1)
    assert result.fetcher == "official_legacy"
    assert result.videos[0].bvid == "BVTEST"
    assert result.videos[0].view_count == 1234
    assert result.videos[0].comment_count == 9
    assert result.videos[0].danmaku_count == 17
    assert result.videos[0].like_count == 31


@pytest.mark.asyncio
async def test_nav_can_supply_wbi_keys_when_not_logged_in() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/x/space/arc/search"):
            return httpx.Response(200, json={"code": -799, "message": "频繁"})
        if request.url.path.endswith("/x/web-interface/nav"):
            return httpx.Response(
                200,
                json={
                    "code": -101,
                    "data": {
                        "wbi_img": {
                            "img_url": "https://i0.hdslb.com/bfs/wbi/" + "a" * 32 + ".png",
                            "sub_url": "https://i0.hdslb.com/bfs/wbi/" + "b" * 32 + ".png",
                        }
                    },
                },
            )
        assert request.url.path.endswith("/x/space/wbi/arc/search")
        return httpx.Response(200, json={"code": -403, "message": "权限"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(BilibiliFetchError) as exc_info:
            await BilibiliClient(http).fetch_user_videos("1", limit=1)
    assert exc_info.value.error_type == "blocked_or_unavailable"
    assert any(item.get("fetcher") == "official_wbi" for item in exc_info.value.attempts)


@pytest.mark.asyncio
async def test_cookie_verification_returns_login_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["cookie"] == "SESSDATA=test"
        assert request.headers["origin"] == "https://www.bilibili.com"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "isLogin": True,
                    "uname": "测试用户",
                    "mid": 7,
                    "level_info": {"current_level": 6},
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await BilibiliClient(
            http, cookie="SESSDATA=test", user_agent="TestBrowser/1.0"
        ).verify_cookie()
    assert result == {
        "configured": True,
        "valid": True,
        "nickname": "测试用户",
        "mid": 7,
        "level": 6,
    }


@pytest.mark.asyncio
async def test_detail_enrichment_is_bounded_and_preserves_zero_values() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/x/space/arc/search"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "list": {
                            "vlist": [
                                {
                                    "bvid": "BVDETAIL",
                                    "aid": 2,
                                    "title": "详情",
                                    "created": 1700000000,
                                    "length": "01:02",
                                    "play": 10,
                                    "comment": 4,
                                },
                            ]
                        }
                    },
                },
            )
        if request.url.path.endswith("/x/web-interface/view"):
            assert request.url.params["bvid"] == "BVDETAIL"
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "stat": {
                            "view": 0,
                            "danmaku": 12,
                            "reply": 0,
                            "like": 8,
                            "coin": 2,
                            "favorite": 3,
                            "share": 1,
                        }
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await BilibiliClient(http).fetch_user_videos("2", limit=1, detail_limit=1)
    video = result.videos[0]
    assert video.view_count == 0
    assert video.comment_count == 0
    assert video.danmaku_count == 12
    assert video.like_count == 8
    assert result.attempts[-1] == {
        "fetcher": "official_detail",
        "bvid": "BVDETAIL",
        "status": "success",
    }
