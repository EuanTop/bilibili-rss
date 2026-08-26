from __future__ import annotations

import hashlib
import time
from urllib.parse import urlencode

# Bilibili web interface signing permutation used by the web client.
MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]


def extract_key(url: str) -> str:
    """Extract the 32-character WBI key from an image URL."""
    name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    return name.rsplit(".", 1)[0]


def mixin_key(img_key: str, sub_key: str) -> str:
    source = img_key + sub_key
    return "".join(source[index] for index in MIXIN_KEY_ENC_TAB if index < len(source))[:32]


def sign_params(
    params: dict[str, object], img_key: str, sub_key: str, *, now: int | None = None
) -> dict[str, str]:
    wts = int(time.time()) if now is None else now
    signed = {str(key): str(value) for key, value in params.items()}
    signed["wts"] = str(wts)
    query = urlencode(sorted(signed.items()))
    query = (
        query.replace("!", "").replace("'", "").replace("(", "").replace(")", "").replace("*", "")
    )
    signed["w_rid"] = hashlib.md5((query + mixin_key(img_key, sub_key)).encode()).hexdigest()
    return signed
