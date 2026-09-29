from __future__ import annotations

import math

from .models import MarketItem


def enrich_and_filter(items: list[MarketItem], config: dict) -> tuple[list[MarketItem], int]:
    """过滤无效商品，并补充最低平台、挂刀比例和 BUFF 市值。"""

    result: list[MarketItem] = []
    skipped = 0
    filters = config["filters"]
    net_rate = float(config["steam"]["net_rate"])
    platforms = config["platforms"]

    for item in items:
        if not item.steam_buy_price or item.steam_buy_price <= 0:
            skipped += 1
            continue
        if item.today_volume is None or (filters["volume"]["enabled"] and item.today_volume <= float(filters["volume"]["min_today_volume"])):
            skipped += 1
            continue
        if not item.buff_sell_price or item.buff_sell_price <= 0 or not item.buff_sell_num or item.buff_sell_num <= 0:
            skipped += 1
            continue
        candidates: list[tuple[str, float, float | None]] = []
        if "BUFF" in platforms and item.buff_sell_price > 0:
            candidates.append(("BUFF", item.buff_sell_price, item.buff_sell_num))
        if "YYYP" in platforms and item.yyyp_sell_price is not None and item.yyyp_sell_price > 0:
            candidates.append(("YYYP", item.yyyp_sell_price, item.yyyp_sell_num))
        if filters["platform_sell_orders"]["enabled"]:
            minimum = float(filters["platform_sell_orders"]["min"])
            candidates = [candidate for candidate in candidates if candidate[2] is not None and candidate[2] >= minimum]
        if not candidates:
            skipped += 1
            continue
        # 同一饰品选择启用平台中的最低购买价。
        platform, price, _ = min(candidates, key=lambda candidate: candidate[1])
        ratio = price / (item.steam_buy_price * net_rate)
        # v1.0 固定使用 BUFF 售价 × BUFF 在售量衡量市场价值。
        market_value = item.buff_sell_price * item.buff_sell_num
        if not math.isfinite(ratio) or ratio <= 0 or not math.isfinite(market_value) or market_value <= 0:
            skipped += 1
            continue
        if filters["price"]["enabled"] and not float(filters["price"]["min"]) <= price <= float(filters["price"]["max"]):
            skipped += 1
            continue
        if filters["ratio"]["enabled"] and not float(filters["ratio"]["min"]) <= ratio <= float(filters["ratio"]["max"]):
            skipped += 1
            continue
        if filters["steam_buy_orders"]["enabled"] and (item.steam_buy_num is None or item.steam_buy_num < float(filters["steam_buy_orders"]["min"])):
            skipped += 1
            continue
        item.best_platform = platform
        item.best_platform_price = price
        item.ratio = ratio
        item.market_value = market_value
        result.append(item)
    return result, skipped
