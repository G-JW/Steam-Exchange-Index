from __future__ import annotations

from datetime import date

from src.notifier import select_level, should_notify


THRESHOLDS = [
    {"value": 0.73, "label": "关注", "priority": 3},
    {"value": 0.71, "label": "机会", "priority": 4},
    {"value": 0.69, "label": "极低", "priority": 5},
]


def test_only_highest_matching_level_is_selected() -> None:
    rank, level = select_level(0.705, THRESHOLDS)
    assert rank == 2
    assert level["value"] == 0.71


def test_cooldown_and_upgrade() -> None:
    state = {"last_notification_date": "2026-09-28", "last_level": 1}
    assert not should_notify(date(2026, 9, 29), 1, state, 3, True)
    assert should_notify(date(2026, 9, 29), 2, state, 3, True)
    assert should_notify(date(2026, 10, 1), 1, state, 3, True)

