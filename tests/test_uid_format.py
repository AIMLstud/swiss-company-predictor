import pytest

from scraper.uid_format import compact_to_formatted, formatted_to_compact

# ── compact_to_formatted ──────────────────────────────────────────────────────

def test_compact_to_formatted_known() -> None:
    assert compact_to_formatted("CHE107251578") == "CHE-107.251.578"


def test_compact_to_formatted_another() -> None:
    assert compact_to_formatted("CHE338108860") == "CHE-338.108.860"


def test_compact_to_formatted_invalid_raises() -> None:
    with pytest.raises(ValueError):
        compact_to_formatted("CHE-107.251.578")   # already formatted


def test_compact_to_formatted_garbage_raises() -> None:
    with pytest.raises(ValueError):
        compact_to_formatted("notauid")


# ── formatted_to_compact ──────────────────────────────────────────────────────

def test_formatted_to_compact_known() -> None:
    assert formatted_to_compact("CHE-107.251.578") == "CHE107251578"


def test_formatted_to_compact_another() -> None:
    assert formatted_to_compact("CHE-338.108.860") == "CHE338108860"


def test_formatted_to_compact_invalid_raises() -> None:
    with pytest.raises(ValueError):
        formatted_to_compact("CHE107251578")   # already compact


def test_formatted_to_compact_garbage_raises() -> None:
    with pytest.raises(ValueError):
        formatted_to_compact("CHE-1.2.3")


# ── roundtrip ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("compact", [
    "CHE107251578",
    "CHE338108860",
    "CHE000000001",
    "CHE999999999",
])
def test_roundtrip(compact: str) -> None:
    assert formatted_to_compact(compact_to_formatted(compact)) == compact
