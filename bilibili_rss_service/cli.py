from __future__ import annotations

import argparse
import getpass
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import uvicorn

from . import __version__
from .config import Settings
from .cookie_input import CookieInputError, NormalizedCookie, normalize_cookie_input
from .service import BilibiliService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bilibili-rss",
        description="Run a small self-hosted RSS service for public Bilibili videos.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="start the HTTP service")
    serve.add_argument("--host", default=None, help="bind address (default: BILIBILI_RSS_HOST)")
    serve.add_argument(
        "--port", type=int, default=None, help="bind port (default: BILIBILI_RSS_PORT)"
    )

    cookie = subparsers.add_parser("cookie", help="manage the local Cookie secret")
    cookie_subparsers = cookie.add_subparsers(dest="cookie_command", required=True)
    cookie_set = cookie_subparsers.add_parser(
        "set", help="read a Cookie securely and write the configured secret file"
    )
    cookie_source = cookie_set.add_mutually_exclusive_group()
    cookie_source.add_argument(
        "--clipboard",
        action="store_true",
        help="read and normalize the complete clipboard contents",
    )
    cookie_source.add_argument(
        "--stdin",
        action="store_true",
        help="read and normalize all input from stdin",
    )
    cookie_subparsers.add_parser("verify", help="verify the configured Cookie against Bilibili")

    subparsers.add_parser("config", help="validate the local configuration").add_argument(
        "action", choices=["check"], nargs="?", default="check"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        settings = Settings.from_env()
        uvicorn.run(
            "bilibili_rss_service.main:app",
            host=args.host or settings.host,
            port=args.port or settings.port,
            factory=False,
        )
        return 0
    if args.command == "cookie" and args.cookie_command == "set":
        return _set_cookie(from_clipboard=args.clipboard, from_stdin=args.stdin)
    if args.command == "cookie" and args.cookie_command == "verify":
        return _verify_cookie()
    if args.command == "config":
        return _check_config()
    return 2


def _settings_and_path() -> tuple[Settings, Path]:
    settings = Settings.from_env()
    return settings, settings.cookie_file.expanduser()


def _set_cookie(*, from_clipboard: bool = False, from_stdin: bool = False) -> int:
    _, path = _settings_and_path()
    try:
        if from_clipboard:
            normalized = normalize_cookie_input(_read_clipboard())
        elif from_stdin:
            normalized = normalize_cookie_input(sys.stdin.read())
        else:
            normalized = _read_interactive_cookie()
    except CookieInputError as exc:
        print(f"Could not parse Cookie input: {exc}", file=sys.stderr)
        return 2
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized.header + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    _print_cookie_summary(normalized)
    print(f"Cookie written to {path} with mode 0600.")
    return 0


def _read_interactive_cookie() -> NormalizedCookie:
    prompt = "Paste Cookie, Cookie header, or one-line cURL (input is hidden): "
    first = normalize_cookie_input(getpass.getpass(prompt))
    second = normalize_cookie_input(getpass.getpass("Paste again to confirm: "))
    if first.header != second.header:
        raise CookieInputError("Cookie confirmation did not match")
    return first


def _print_cookie_summary(cookie: NormalizedCookie) -> None:
    fields = ", ".join(
        f"{name}={'yes' if present else 'no'}" for name, present in cookie.login_fields.items()
    )
    print(f"Detected {len(cookie.names)} Cookie fields from {cookie.source_format} input.")
    print(f"Login fields: {fields}")
    if not cookie.login_fields["SESSDATA"]:
        print("Warning: SESSDATA was not detected; login verification may fail.", file=sys.stderr)


def _read_clipboard() -> str:
    system = platform.system()
    candidates: list[list[str]]
    if system == "Darwin":
        candidates = [["pbpaste"]]
    elif system == "Windows":
        candidates = [["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]]
    else:
        candidates = [
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ]
    for command in candidates:
        if shutil.which(command[0]) is None:
            continue
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout:
            return result.stdout
    raise CookieInputError(
        "Clipboard access is unavailable. Use `cookie set --stdin` or the hidden prompt."
    )


def _verify_cookie() -> int:
    settings, path = _settings_and_path()
    if not path.is_file():
        print(f"Cookie file not found: {path}", file=sys.stderr)
        return 2
    result = _run_async(_verify(settings))
    configured = bool(result.get("configured"))
    valid = bool(result.get("valid"))
    print(f"configured: {'yes' if configured else 'no'}")
    print(f"valid: {'yes' if valid else 'no'}")
    if result.get("nickname"):
        print(f"nickname: {result['nickname']}")
    if result.get("reason"):
        print(f"reason: {result['reason']}")
    return 0 if valid else 1


def _check_config() -> int:
    settings, path = _settings_and_path()
    print(f"listen: {settings.host}:{settings.port}")
    print(f"cookie_file: {path}")
    print(f"cookie_configured: {'yes' if path.is_file() and bool(settings.cookie) else 'no'}")
    print(f"data_dir: {settings.data_dir}")
    return 0


async def _verify(settings: Settings) -> dict[str, object]:
    service = BilibiliService(settings)
    try:
        return await service.verify_cookie()
    finally:
        await service.close()


def _run_async(awaitable):
    import asyncio

    return asyncio.run(awaitable)


if __name__ == "__main__":
    raise SystemExit(main())
