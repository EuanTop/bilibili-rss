from bilibili_rss_service.cli import build_parser


def test_cli_exposes_service_commands() -> None:
    assert build_parser().parse_args(["serve"]).command == "serve"
    args = build_parser().parse_args(["cookie", "set"])
    assert args.command == "cookie"
    assert args.cookie_command == "set"
    assert args.clipboard is False
    assert args.stdin is False

    clipboard_args = build_parser().parse_args(["cookie", "set", "--clipboard"])
    assert clipboard_args.clipboard is True
