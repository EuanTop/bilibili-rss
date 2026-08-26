from pathlib import Path

from bilibili_rss_service.config import Settings


def test_cookie_is_read_from_file_only(tmp_path: Path, monkeypatch) -> None:
    cookie_file = tmp_path / "bilibili.cookie"
    cookie_file.write_text("SESSDATA=file-value\n", encoding="utf-8")
    monkeypatch.setenv("BILIBILI_COOKIE_FILE", str(cookie_file))
    monkeypatch.setenv("BILIBILI_COOKIE", "env-value")

    settings = Settings.from_env(env_file=tmp_path / "missing.env")

    assert settings.cookie == "SESSDATA=file-value"
    assert settings.cookie_file == cookie_file


def test_settings_bound_audit_configuration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BILIBILI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BILIBILI_AUDIT_MAX_BYTES", "1")
    monkeypatch.setenv("BILIBILI_AUDIT_BACKUP_COUNT", "99")

    settings = Settings.from_env(env_file=tmp_path / "missing.env")

    assert settings.audit_max_bytes == 1024
    assert settings.audit_backup_count == 10
