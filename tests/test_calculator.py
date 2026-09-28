from __future__ import annotations

import math

import pytest

from src.calculator import calculate_indexes
from src.filters import enrich_and_filter
from src.models import MarketItem


def item(name: str, buff: float = 70, yyyp: float | None = 68, steam: float = 100, volume: float = 101, buff_num: float = 10) -> MarketItem:
    return MarketItem(name, name, steam, 10, volume, buff, buff_num, yyyp, 10)


def test_ratio_and_lower_platform_selected(config: dict) -> None:
    config["filters"]["ratio"]["enabled"] = False
    valid, skipped = enrich_and_filter([item("A")], config)
    assert skipped == 0
    assert valid[0].best_platform == "YYYP"
    assert valid[0].ratio == pytest.approx(68 / (100 * 0.869))
    assert valid[0].market_value == 700


def test_volume_filter_is_strictly_greater(config: dict) -> None:
    config["filters"]["ratio"]["enabled"] = False
    valid, skipped = enrich_and_filter([item("equal", volume=100), item("above", volume=101)], config)
    assert [entry.name for entry in valid] == ["above"]
    assert skipped == 1


@pytest.mark.parametrize(
    "bad",
    [
        item("steam-zero", steam=0),
        item("buff-zero", buff=0),
        item("buff-num-zero", buff_num=0),
        item("nan-ratio", steam=math.nan),
        item("inf-ratio", steam=math.inf),
    ],
)
def test_invalid_data_is_skipped(config: dict, bad: MarketItem) -> None:
    config["filters"]["ratio"]["enabled"] = False
    valid, skipped = enrich_and_filter([bad], config)
    assert valid == []
    assert skipped == 1


def valued_item(name: str, ratio: float, value: float) -> MarketItem:
    entry = item(name)
    entry.ratio = ratio
    entry.market_value = value
    return entry


def test_index_uses_full_boundary_item() -> None:
    entries = [valued_item("A", 0.68, 10), valued_item("B", 0.70, 20), valued_item("C", 0.75, 70)]
    indexes = calculate_indexes(entries, [0.05, 0.10, 0.20])
    assert indexes[0.05] == pytest.approx(0.68)
    assert indexes[0.10] == pytest.approx(0.68)
    assert indexes[0.20] == pytest.approx((0.68 * 10 + 0.70 * 20) / 30)
