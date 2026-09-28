from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import quote

import requests

from .models import MarketItem


class NotificationError(RuntimeError):
    pass


def select_level(index: float, thresholds: list[dict[str, Any]]) -> tuple[int, dict[str, Any]] | None:
    ordered = sorted(thresholds, key=lambda threshold: float(threshold["value"]), reverse=True)
    matches = [(rank, threshold) for rank, threshold in enumerate(ordered, start=1) if index <= float(threshold["value"])]
    return matches[-1] if matches else None


def load_state(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def should_notify(today: date, level: int, state: dict[str, Any], cooldown_days: int, allow_upgrade: bool) -> bool:
    try:
        last_date = date.fromisoformat(str(state["last_notification_date"]))
        last_level = int(state["last_level"])
    except (KeyError, TypeError, ValueError):
        return True
    if allow_upgrade and level > last_level:
        return True
    return today >= last_date + timedelta(days=cooldown_days)


def save_state(path: str | Path, state: dict[str, Any]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=state_path.parent, delete=False) as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, state_path)


def format_message(run_date: date, indexes: dict[float, float], valid_count: int, stats: dict[str, float | None], items: list[MarketItem]) -> str:
    lines = [
        f"日期: {run_date.isoformat()}",
        f"I5: {indexes[0.05]:.4f}",
        f"I10: {indexes[0.10]:.4f}",
        f"I20: {indexes[0.20]:.4f}",
        f"有效饰品: {valid_count}",
    ]
    for key, label in (("ma7", "MA7"), ("ma30", "MA30")):
        if stats.get(key) is not None:
            lines.append(f"{label}: {stats[key]:.4f}")
    for key, label in (("p30", "30日位置"), ("p90", "90日位置"), ("p365", "365日位置")):
        if stats.get(key) is not None:
            lines.append(f"{label}: {stats[key]:.1f}%")
    if items:
        lines.append("")
        lines.append("Top 挂刀候选:")
        for number, item in enumerate(items, start=1):
            lines.append(f"{number}. {item.name} | {item.ratio:.4f} | {item.best_platform} ¥{item.best_platform_price:.2f} | Steam求购 ¥{item.steam_buy_price:.2f} | 成交量 {item.today_volume:g}")
    return "\n".join(lines)


def post_ntfy(url: str, title: str, message: str, priority: int, timeout: float = 15) -> None:
    try:
        response = requests.post(
            url,
            data=message.encode("utf-8"),
            headers={"Title": quote(title), "Priority": str(priority), "Tags": "chart_with_upwards_trend"},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # NTFY_URL may itself be a secret topic URL; do not include the request
        # exception text because requests commonly embeds the full URL in it.
        raise NotificationError(f"ntfy 发送失败（{type(exc).__name__}）") from exc
