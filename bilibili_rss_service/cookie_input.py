from __future__ import annotations

import json
import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

MAX_INPUT_BYTES = 1024 * 1024
MAX_COOKIE_BYTES = 64 * 1024
COOKIE_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
COOKIE_ATTRIBUTES = {
    "domain",
    "expires",
    "httponly",
    "max-age",
    "partitioned",
    "path",
    "priority",
    "samesite",
    "secure",
}
LOGIN_COOKIE_NAMES = ("SESSDATA", "bili_jct", "DedeUserID")


class CookieInputError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedCookie:
    header: str
    names: tuple[str, ...]
    source_format: str

    @property
    def login_fields(self) -> dict[str, bool]:
        present = set(self.names)
        return {name: name in present for name in LOGIN_COOKIE_NAMES}


def normalize_cookie_input(raw: str) -> NormalizedCookie:
    text = raw.strip("\ufeff \t\r\n")
    if not text:
        raise CookieInputError("Cookie input is empty")
    if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        raise CookieInputError("Cookie input is larger than 1 MiB")
    if "\x00" in text:
        raise CookieInputError("Cookie input contains a null byte")
    text = _unwrap_console_value(text)

    parsers = (
        ("json", _pairs_from_json),
        ("curl", _pairs_from_curl),
        ("netscape", _pairs_from_netscape),
        ("table", _pairs_from_table),
        ("header", _pairs_from_headers),
        ("raw", _pairs_from_raw),
    )
    for source_format, parser in parsers:
        pairs = parser(text)
        normalized = _normalize_pairs(pairs)
        if normalized:
            header = "; ".join(f"{name}={value}" for name, value in normalized)
            if len(header.encode("utf-8")) > MAX_COOKIE_BYTES:
                raise CookieInputError("Normalized Cookie is larger than 64 KiB")
            return NormalizedCookie(
                header=header,
                names=tuple(name for name, _ in normalized),
                source_format=source_format,
            )
    raise CookieInputError(
        "No Cookie fields were found. Copy a Cookie header, cURL request, browser table, "
        "JSON export, or Netscape cookie file."
    )


def _pairs_from_json(text: str) -> list[tuple[str, str]]:
    if not text.startswith(("[", "{")):
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    return _json_cookie_pairs(payload)


def _json_cookie_pairs(payload: Any) -> list[tuple[str, str]]:
    if isinstance(payload, dict) and isinstance(payload.get("name"), str):
        value = payload.get("value")
        if isinstance(value, (str, int, float)):
            return [(payload["name"], str(value))]
    if isinstance(payload, dict) and isinstance(payload.get("cookies"), list):
        payload = payload["cookies"]
    if isinstance(payload, dict):
        for key in ("cookie", "Cookie", "cookieHeader"):
            if isinstance(payload.get(key), str):
                return _pairs_from_headers(f"Cookie: {payload[key]}")
    if isinstance(payload, list):
        pairs: list[tuple[str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if isinstance(name, str) and isinstance(value, (str, int, float)):
                pairs.append((name, str(value)))
        return pairs
    if isinstance(payload, dict):
        pairs = []
        for name, value in payload.items():
            if isinstance(value, (str, int, float)):
                pairs.append((str(name), str(value)))
        return pairs
    return []


def _unwrap_console_value(text: str) -> str:
    assignment = re.match(r"^\s*document\.cookie\s*=\s*(.+)$", text, re.DOTALL)
    if assignment:
        text = assignment.group(1).strip()
    if len(text) >= 2 and text[0] in {'"', "'"} and text[-1] == text[0]:
        return text[1:-1]
    return text


def _pairs_from_curl(text: str) -> list[tuple[str, str]]:
    if not re.search(r"(?:^|\s)curl(?:\s|$)", text, re.IGNORECASE):
        return []
    try:
        tokens = shlex.split(text.replace("\\\r\n", " ").replace("\\\n", " "))
    except ValueError:
        return []
    values: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"-H", "--header", "-b", "--cookie"} and index + 1 < len(tokens):
            candidate = tokens[index + 1]
            if token in {"-b", "--cookie"}:
                values.append(candidate)
            elif candidate.lower().startswith("cookie:"):
                values.append(candidate.split(":", 1)[1].strip())
            index += 2
            continue
        if token.startswith("--cookie="):
            values.append(token.split("=", 1)[1])
        index += 1
    return _split_cookie_values(values)


def _pairs_from_netscape(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    saw_netscape = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or (stripped.startswith("#") and not stripped.startswith("#HttpOnly_")):
            continue
        columns = stripped.split("\t")
        if len(columns) >= 7 and columns[1].upper() in {"TRUE", "FALSE"}:
            saw_netscape = True
            pairs.append((columns[-2], columns[-1]))
    return pairs if saw_netscape else []


def _pairs_from_table(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    saw_table = False
    for line in text.splitlines():
        columns = [column.strip() for column in line.split("\t")]
        if len(columns) < 2:
            continue
        if columns[0].lower() == "name" and columns[1].lower() == "value":
            saw_table = True
            continue
        if COOKIE_NAME_RE.fullmatch(columns[0]):
            saw_table = True
            pairs.append((columns[0], columns[1]))
    return pairs if saw_table else []


def _pairs_from_headers(text: str) -> list[tuple[str, str]]:
    values: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*cookie\s*:\s*(.+)$", line, re.IGNORECASE)
        if match:
            values.append(match.group(1))
            continue
        match = re.match(r"^\s*set-cookie\s*:\s*(.+)$", line, re.IGNORECASE)
        if match:
            values.append(match.group(1).split(";", 1)[0])
    return _split_cookie_values(values)


def _pairs_from_raw(text: str) -> list[tuple[str, str]]:
    if "\n" in text or "\r" in text:
        return []
    if re.search(r"(?:^|\s)curl(?:\s|$)", text, re.IGNORECASE):
        return []
    value = re.sub(r"^\s*cookie\s*:\s*", "", text, flags=re.IGNORECASE)
    return _split_cookie_values([value])


def _split_cookie_values(values: Iterable[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for value in values:
        for part in value.split(";"):
            name, separator, cookie_value = part.strip().partition("=")
            if separator:
                pairs.append((name, cookie_value))
    return pairs


def _normalize_pairs(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    normalized: dict[str, str] = {}
    for raw_name, raw_value in pairs:
        name = raw_name.strip()
        value = raw_value.strip()
        if not name or name.lower() in COOKIE_ATTRIBUTES:
            continue
        if not COOKIE_NAME_RE.fullmatch(name):
            continue
        if value.startswith(('"', "'")) and value.endswith(value[0]) and len(value) >= 2:
            value = value[1:-1]
        if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
            raise CookieInputError(f"Cookie field {name!r} contains a control character")
        normalized[name] = value
    return list(normalized.items())
