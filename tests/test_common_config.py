import pytest
from pydantic import ValidationError

from common.config import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ZEFIX_USERNAME", "user")
    monkeypatch.setenv("ZEFIX_PASSWORD", "pass")
    monkeypatch.delenv("ZEFIX_SLEEP_BETWEEN", raising=False)
    monkeypatch.delenv("HR_SLEEP_BETWEEN", raising=False)
    s = Settings(_env_file=None)
    assert s.zefix_canton == "LU"
    assert s.zefix_sleep_between == 0.1
    assert s.hr_sleep_between == 0.2
    assert s.hr_concurrency == 4
    assert s.hr_max_retries == 3


def test_custom_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ZEFIX_USERNAME", "myuser")
    monkeypatch.setenv("ZEFIX_PASSWORD", "mypass")
    monkeypatch.setenv("ZEFIX_SLEEP_BETWEEN", "0.5")
    monkeypatch.setenv("HR_SLEEP_BETWEEN", "0.1")
    monkeypatch.setenv("HR_CONCURRENCY", "8")
    s = Settings(_env_file=None)
    assert s.zefix_username == "myuser"
    assert s.zefix_sleep_between == 0.5
    assert s.hr_sleep_between == 0.1
    assert s.hr_concurrency == 8


def test_missing_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_DB_URL", raising=False)
    monkeypatch.delenv("ZEFIX_USERNAME", raising=False)
    monkeypatch.delenv("ZEFIX_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_seed_csv_path_is_path_object(monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    monkeypatch.setenv("APP_DB_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ZEFIX_USERNAME", "user")
    monkeypatch.setenv("ZEFIX_PASSWORD", "pass")
    s = Settings(_env_file=None)
    assert isinstance(s.seed_csv_path, Path)
