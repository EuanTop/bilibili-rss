from bilibili_rss_service.wbi import MIXIN_KEY_ENC_TAB, extract_key, mixin_key, sign_params


def test_extract_key_and_sign_params_are_stable() -> None:
    img = extract_key("https://i0.hdslb.com/bfs/wbi/" + "a" * 32 + ".png")
    sub = extract_key("https://i0.hdslb.com/bfs/wbi/" + "b" * 32 + ".png")
    assert img == "a" * 32
    assert sub == "b" * 32
    assert len(mixin_key(img, sub)) == 32
    assert len(MIXIN_KEY_ENC_TAB) == 64
    signed = sign_params({"mid": 123, "ps": 10}, img, sub, now=1700000000)
    assert signed["wts"] == "1700000000"
    assert len(signed["w_rid"]) == 32
