import pandas as pd
import pytest

from training.split import temporal_split


def _df(weeks: list[tuple[int, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "iso_year": [y for y, _ in weeks],
            "iso_week": [w for _, w in weeks],
            "n_registrations": range(1, len(weeks) + 1),
        }
    )


# ── basic correctness ─────────────────────────────────────────────────────────


def test_split_partitions_all_rows() -> None:
    df = _df([(2022, w) for w in range(1, 11)])
    sp = temporal_split(df, val_start=(2022, 7), test_start=(2022, 9))
    assert len(sp.train) + len(sp.val) + len(sp.test) == len(df)


def test_split_no_overlap() -> None:
    df = _df([(2022, w) for w in range(1, 11)])
    sp = temporal_split(df, val_start=(2022, 7), test_start=(2022, 9))
    train_keys = set(zip(sp.train["iso_year"], sp.train["iso_week"], strict=True))
    val_keys = set(zip(sp.val["iso_year"], sp.val["iso_week"], strict=True))
    test_keys = set(zip(sp.test["iso_year"], sp.test["iso_week"], strict=True))
    assert train_keys.isdisjoint(val_keys)
    assert train_keys.isdisjoint(test_keys)
    assert val_keys.isdisjoint(test_keys)


def test_split_boundaries_inclusive() -> None:
    df = _df([(2022, 6), (2022, 7), (2022, 8), (2022, 9), (2022, 10)])
    sp = temporal_split(df, val_start=(2022, 7), test_start=(2022, 9))
    assert list(sp.train["iso_week"]) == [6]
    assert list(sp.val["iso_week"]) == [7, 8]
    assert list(sp.test["iso_week"]) == [9, 10]


def test_split_ordering() -> None:
    df = _df([(2022, w) for w in range(1, 20)])
    sp = temporal_split(df, val_start=(2022, 10), test_start=(2022, 15))
    assert sp.train["iso_week"].max() < 10
    assert sp.val["iso_week"].min() >= 10
    assert sp.val["iso_week"].max() < 15
    assert sp.test["iso_week"].min() >= 15


def test_split_empty_val_when_same_boundary() -> None:
    df = _df([(2022, w) for w in range(1, 6)])
    sp = temporal_split(df, val_start=(2022, 4), test_start=(2022, 4))
    assert len(sp.val) == 0
    assert len(sp.train) + len(sp.test) == len(df)


def test_split_raises_when_val_after_test() -> None:
    df = _df([(2022, w) for w in range(1, 5)])
    with pytest.raises(ValueError):
        temporal_split(df, val_start=(2022, 5), test_start=(2022, 3))


# ── KW53 edge cases ───────────────────────────────────────────────────────────

_KW53 = [(2020, 51), (2020, 52), (2020, 53), (2021, 1), (2021, 2)]


def test_kw53_boundary_in_val() -> None:
    sp = temporal_split(_df(_KW53), val_start=(2020, 53), test_start=(2021, 2))
    assert list(zip(sp.train["iso_year"], sp.train["iso_week"], strict=True)) == [
        (2020, 51),
        (2020, 52),
    ]
    assert list(zip(sp.val["iso_year"], sp.val["iso_week"], strict=True)) == [
        (2020, 53),
        (2021, 1),
    ]
    assert list(zip(sp.test["iso_year"], sp.test["iso_week"], strict=True)) == [(2021, 2)]


def test_kw53_in_train() -> None:
    sp = temporal_split(_df(_KW53), val_start=(2021, 1), test_start=(2021, 2))
    train_keys = list(zip(sp.train["iso_year"], sp.train["iso_week"], strict=True))
    assert (2020, 53) in train_keys
    assert (2021, 1) not in train_keys


def test_kw53_is_after_week52_same_year() -> None:
    df = _df([(2020, 52), (2020, 53), (2021, 1)])
    sp = temporal_split(df, val_start=(2020, 53), test_start=(2021, 1))
    assert len(sp.train) == 1 and sp.train.iloc[0]["iso_week"] == 52
    assert len(sp.val) == 1 and sp.val.iloc[0]["iso_week"] == 53
    assert len(sp.test) == 1 and sp.test.iloc[0]["iso_week"] == 1


def test_kw53_is_before_week1_next_year() -> None:
    df = _df([(2020, 53), (2021, 1)])
    sp = temporal_split(df, val_start=(2021, 1), test_start=(2021, 52))
    # 2020-W53 must land in train, not val
    assert sp.train.iloc[0]["iso_year"] == 2020
    assert sp.train.iloc[0]["iso_week"] == 53
    assert sp.val.iloc[0]["iso_week"] == 1
