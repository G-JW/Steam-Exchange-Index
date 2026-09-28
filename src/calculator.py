from __future__ import annotations

import math

from .models import MarketItem


class CalculationError(RuntimeError):
    pass


def calculate_indexes(items: list[MarketItem], percentiles: list[float]) -> dict[float, float]:
    if not items:
        raise CalculationError("没有有效饰品可计算指数")
    ordered = sorted(items, key=lambda item: float(item.ratio))
    total_value = sum(float(item.market_value) for item in ordered)
    if not math.isfinite(total_value) or total_value <= 0:
        raise CalculationError("无法计算有效市场总价值")
    indexes: dict[float, float] = {}
    for percentile in percentiles:
        target = float(percentile) * total_value
        selected_value = weighted_sum = 0.0
        for item in ordered:
            value = float(item.market_value)
            selected_value += value
            weighted_sum += float(item.ratio) * value
            if selected_value >= target:
                break
        index = weighted_sum / selected_value
        if not math.isfinite(index):
            raise CalculationError(f"指数 I{int(percentile * 100)} 不是有限数")
        indexes[float(percentile)] = index
    return indexes


def top_items(items: list[MarketItem], count: int) -> list[MarketItem]:
    return sorted(items, key=lambda item: float(item.ratio))[:count]

