from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class MarketItem:
    item_id: str
    name: str
    steam_buy_price: float | None
    steam_buy_num: float | None
    today_volume: float | None
    buff_sell_price: float | None
    buff_sell_num: float | None
    yyyp_sell_price: float | None
    yyyp_sell_num: float | None
    best_platform: str | None = None
    best_platform_price: float | None = None
    ratio: float | None = None
    market_value: float | None = None

