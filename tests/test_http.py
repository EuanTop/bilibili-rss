from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from bilibili_rss_service import main
from bilibili_rss_service.client import BilibiliFetchError
from bilibili_rss_service.main import app


def test_service_home_health_and_stylesheet_are_available() -> None:
    with TestClient(app) as client:
        home = client.get("/")
        health = client.get("/health")
        compatibility_health = client.get("/api/health")
        stylesheet = client.get("/static/rss.xsl")

    assert home.status_code == 200
    assert "Bilibili RSS Service" in home.text
    assert health.json()["ok"] is True
    assert compatibility_health.json()["service"] == "bilibili-rss"
    assert stylesheet.status_code == 200
    assert "xsl:stylesheet" in stylesheet.text


def test_rss_base_path_redirects_to_usage_page() -> None:
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/rss")

    assert response.status_code == 307
    assert response.headers["location"] == "/"


def test_cookie_verification_is_not_an_http_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/cookie/verify")

    assert response.status_code == 404


def test_invalid_uid_returns_bad_request(monkeypatch) -> None:
    monkeypatch.setattr(
        main.service,
        "fetch",
        AsyncMock(
            side_effect=BilibiliFetchError(
                "uid must contain 1-20 digits",
                error_type="invalid_input",
            )
        ),
    )
    with TestClient(app) as client:
        response = client.get("/rss/not-a-uid")

    assert response.status_code == 400
    assert response.json()["detail"]["errorType"] == "invalid_input"


def test_rss_enriches_five_items_by_default(monkeypatch) -> None:
    fetch = AsyncMock(
        side_effect=BilibiliFetchError("upstream unavailable", error_type="fetch_error")
    )
    monkeypatch.setattr(main.service, "fetch", fetch)

    with TestClient(app) as client:
        response = client.get("/rss/546195")

    assert response.status_code == 502
    fetch.assert_awaited_once_with("546195", force=False, detail_limit=5)
