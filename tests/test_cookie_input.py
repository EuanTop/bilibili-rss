import pytest

from bilibili_rss_service.cookie_input import CookieInputError, normalize_cookie_input


def test_normalizes_raw_cookie_header_and_filters_attributes() -> None:
    cookie = normalize_cookie_input(
        "Cookie: SESSDATA=first; bili_jct=csrf; Path=/; HttpOnly; SESSDATA=latest"
    )

    assert cookie.header == "SESSDATA=latest; bili_jct=csrf"
    assert cookie.source_format == "header"
    assert cookie.login_fields == {
        "SESSDATA": True,
        "bili_jct": True,
        "DedeUserID": False,
    }


def test_extracts_cookie_from_multiline_curl() -> None:
    cookie = normalize_cookie_input(
        """curl 'https://api.bilibili.com/x/web-interface/nav' \\
  -H 'accept: application/json' \\
  -H 'cookie: SESSDATA=session; bili_jct=csrf; DedeUserID=7'"""
    )

    assert cookie.source_format == "curl"
    assert cookie.header == "SESSDATA=session; bili_jct=csrf; DedeUserID=7"


def test_extracts_cookie_from_browser_json_export() -> None:
    cookie = normalize_cookie_input(
        '[{"name":"SESSDATA","value":"session"},{"name":"bili_jct","value":"csrf"}]'
    )

    assert cookie.source_format == "json"
    assert cookie.header == "SESSDATA=session; bili_jct=csrf"


def test_extracts_quoted_console_value_without_losing_first_field() -> None:
    cookie = normalize_cookie_input("'buvid3=device; bili_jct=csrf'")

    assert cookie.source_format == "raw"
    assert cookie.header == "buvid3=device; bili_jct=csrf"


def test_extracts_cookie_from_devtools_table() -> None:
    cookie = normalize_cookie_input(
        "Name\tValue\tDomain\tPath\n"
        "SESSDATA\tsession\t.bilibili.com\t/\n"
        "bili_jct\tcsrf\t.bilibili.com\t/"
    )

    assert cookie.source_format == "table"
    assert cookie.header == "SESSDATA=session; bili_jct=csrf"


def test_extracts_cookie_from_netscape_file() -> None:
    cookie = normalize_cookie_input(
        "# Netscape HTTP Cookie File\n"
        "#HttpOnly_.bilibili.com\tTRUE\t/\tTRUE\t1999999999\tSESSDATA\tsession\n"
        ".bilibili.com\tTRUE\t/\tFALSE\t1999999999\tbili_jct\tcsrf"
    )

    assert cookie.source_format == "netscape"
    assert cookie.header == "SESSDATA=session; bili_jct=csrf"


def test_rejects_unrecognized_or_unsafe_input() -> None:
    with pytest.raises(CookieInputError, match="No Cookie fields"):
        normalize_cookie_input("curl this-is-not-a-valid-cookie")
    with pytest.raises(CookieInputError, match="control character"):
        normalize_cookie_input('[{"name":"SESSDATA","value":"bad\\nvalue"}]')
