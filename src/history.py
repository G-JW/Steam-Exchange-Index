from __future__ import annotations

import csv
import math
import os
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


FIELDNAMES = ["date", "run_timestamp", "index_5", "index_10", "index_20", "valid_items", "min_ratio", "ma7", "ma30", "p30", "p180"]
REQUIRED_HISTORY_FIELDS = {"date", "run_timestamp", "index_5", "index_10", "index_20", "valid_items", "min_ratio"}


def load_history(path: str | Path) -> list[dict[str, str]]:
    """读取历史；兼容早期版本多出的统计列。"""

    history_path = Path(path)
    if not history_path.exists() or history_path.stat().st_size == 0:
        return []
    with history_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED_HISTORY_FIELDS.issubset(reader.fieldnames):
            raise ValueError(f"历史 CSV 缺少必要字段: {','.join(sorted(REQUIRED_HISTORY_FIELDS))}")
        return [{field: row.get(field, "") for field in FIELDNAMES} for row in reader]


def _valid_previous(rows: list[dict[str, str]], current_date: str) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = []
    for row in rows:
        try:
            value = float(row["index_10"])
            parsed_date = date.fromisoformat(row["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if parsed_date < date.fromisoformat(current_date) and math.isfinite(value):
            values.append((row["date"], value))
    return sorted(values, key=lambda pair: pair[0])


def calculate_statistics(rows: list[dict[str, str]], current_date: str, current_index: float, moving_averages: list[int], percentile_windows: list[int]) -> dict[str, float | None]:
    """计算移动平均及当前 I10 的历史低位百分比。"""

    previous = _valid_previous(rows, current_date)
    stats: dict[str, float | None] = {}
    for window in moving_averages:
        prior = [value for _, value in previous[-(window - 1):]] if window > 1 else []
        samples = prior + [current_index]
        stats[f"ma{window}"] = sum(samples) / window if len(samples) == window else None
    for window in percentile_windows:
        # 当前值越低于更多历史日期，百分比越高，代表挂刀折扣越突出。
        samples = [value for _, value in previous[-window:]]
        stats[f"p{window}"] = (sum(value > current_index for value in samples) / window * 100) if len(samples) == window else None
    return stats


def _format(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.8f}".rstrip("0").rstrip(".")
    return str(value)


def upsert_history(path: str | Path, row: dict[str, Any]) -> None:
    """按日期覆盖写入，保证同一天最多一条记录。"""

    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    rows = load_history(history_path)
    normalized = {field: _format(row.get(field)) for field in FIELDNAMES}
    rows = [existing for existing in rows if existing.get("date") != normalized["date"]]
    rows.append(normalized)
    rows.sort(key=lambda existing: existing["date"])
    with NamedTemporaryFile("w", newline="", encoding="utf-8", dir=history_path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.replace(temporary, history_path)


def make_history_row(run_time: datetime, indexes: dict[float, float], valid_items: int, min_ratio: float, stats: dict[str, float | None]) -> dict[str, Any]:
    return {
        "date": run_time.date().isoformat(),
        "run_timestamp": run_time.isoformat(timespec="seconds"),
        "index_5": indexes[0.05],
        "index_10": indexes[0.10],
        "index_20": indexes[0.20],
        "valid_items": valid_items,
        "min_ratio": min_ratio,
        "ma7": stats.get("ma7"),
        "ma30": stats.get("ma30"),
        "p30": stats.get("p30"),
        "p180": stats.get("p180"),
    }
