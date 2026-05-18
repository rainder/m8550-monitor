import os
import pytest
from m8550_collector.config import Config, load_config


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("M8550_HOST", "192.168.1.1")
    monkeypatch.setenv("M8550_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", "/data/m8550.db")
    monkeypatch.setenv("POLL_INTERVAL", "5")
    monkeypatch.setenv("AUTH_BACKOFF_SECONDS", "120")

    cfg = load_config()

    assert cfg == Config(
        host="192.168.1.1",
        password="secret",
        db_path="/data/m8550.db",
        poll_interval=5,
        auth_backoff_seconds=120,
    )


def test_load_config_default_interval(monkeypatch):
    monkeypatch.setenv("M8550_HOST", "192.168.1.1")
    monkeypatch.setenv("M8550_PASSWORD", "secret")
    monkeypatch.setenv("DB_PATH", "/data/m8550.db")
    monkeypatch.delenv("POLL_INTERVAL", raising=False)
    monkeypatch.delenv("AUTH_BACKOFF_SECONDS", raising=False)

    cfg = load_config()

    assert cfg.poll_interval == 5
    assert cfg.auth_backoff_seconds == 300


def test_load_config_missing_password_raises(monkeypatch):
    monkeypatch.setenv("M8550_HOST", "192.168.1.1")
    monkeypatch.delenv("M8550_PASSWORD", raising=False)
    monkeypatch.setenv("DB_PATH", "/data/m8550.db")

    with pytest.raises(KeyError, match="M8550_PASSWORD"):
        load_config()
