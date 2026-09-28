from __future__ import annotations

from datetime import datetime

import pytest

from src.history import calculate_statistics, load_history, upsert_history


def row(day: str, index: float) -> dict[str, str]:
    return {"date": day, "index_10": str(index)}


def test_historical_percentile_excludes_current_and_requires_full_window() -> None:
    rows = [row("2026-01-01", 0.75), row("2026-01-02", 0.73), row("2026-01-03", 0.72), row("2026-01-04", 0.70)]
    stats = calculate_statistics(rows, "2026-01-05", 0.71, [3], [4, 5])
    assert stats["ma3"] == pytest.approx((0.72 + 0.70 + 0.71) / 3)
    assert stats["p4"] == 75
    assert stats["p5"] is None


def test_history_upsert_is_idempotent(tmp_path) -> None:
    path = tmp_path / "index.csv"
    base = {
        "date": "2026-09-29",
        "run_timestamp": datetime(2026, 9, 29, 12).isoformat(),
        "index_5": 0.68,
        "index_10": 0.70,
        "index_20": 0.72,
        "valid_items": 100,
        "min_ratio": 0.65,
    }
    upsert_history(path, base)
    upsert_history(path, {**base, "index_10": 0.69})
    rows = load_history(path)
    assert len(rows) == 1
    assert float(rows[0]["index_10"]) == 0.69

