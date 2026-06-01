from unittest.mock import MagicMock, patch

import pytest

import common.db as db_module


@pytest.fixture(autouse=True)
def reset_engine() -> None:
    """Reset the module-level engine singleton before and after each test."""
    db_module._engine = None
    yield
    db_module._engine = None


def _mock_settings(url: str = "postgresql+psycopg://u:p@localhost/db") -> MagicMock:
    s = MagicMock()
    s.app_db_url = url
    return s


def test_get_engine_singleton() -> None:
    with (
        patch("common.db.get_settings", return_value=_mock_settings()),
        patch("common.db.create_engine") as mock_create,
    ):
        mock_create.return_value = MagicMock()
        e1 = db_module.get_engine()
        e2 = db_module.get_engine()

    assert e1 is e2
    mock_create.assert_called_once()


def test_get_engine_passes_url() -> None:
    url = "postgresql+psycopg://u:p@localhost/mydb"
    with (
        patch("common.db.get_settings", return_value=_mock_settings(url)),
        patch("common.db.create_engine") as mock_create,
    ):
        mock_create.return_value = MagicMock()
        db_module.get_engine()

    mock_create.assert_called_once_with(url, pool_pre_ping=True)


def test_get_session_commits_on_success() -> None:
    mock_session = MagicMock()
    mock_engine = MagicMock()

    with (
        patch("common.db.get_engine", return_value=mock_engine),
        patch("common.db.Session") as mock_session_cls,
    ):
        mock_session_cls.return_value.__enter__ = lambda s: mock_session
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        with db_module.get_session() as session:
            assert session is mock_session

    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()


def test_get_session_rolls_back_on_error() -> None:
    mock_session = MagicMock()
    mock_engine = MagicMock()

    with (
        patch("common.db.get_engine", return_value=mock_engine),
        patch("common.db.Session") as mock_session_cls,
    ):
        mock_session_cls.return_value.__enter__ = lambda s: mock_session
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(ValueError), db_module.get_session():
            raise ValueError("boom")

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
