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


def test_legacy_history_schema_is_migrated_on_write(tmp_path) -> None:
    path = tmp_path / "legacy.csv"
    path.write_text(
        "date,run_timestamp,index_5,index_10,index_20,valid_items,min_ratio,ma7,ma30,p30,p90,p365\n"
        "2026-09-29,2026-09-29T23:40:00+08:00,0.68,0.70,0.72,100,0.65,,,,,\n",
        encoding="utf-8",
    )
    rows = load_history(path)
    assert rows[0]["p180"] == ""
    upsert_history(path, {**rows[0], "p180": 91.0})
    assert "p180" in path.read_text(encoding="utf-8").splitlines()[0]
