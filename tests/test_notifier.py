from __future__ import annotations

import pytest

from src.notifier import NotificationError, format_message, is_special_alert, post_ntfy, resolve_ntfy_target


def test_message_contains_only_three_indexes() -> None:
    message = format_message({0.05: 0.71, 0.10: 0.73, 0.20: 0.76})
    assert message == "I5 = 0.7100\nI10 = 0.7300\nI20 = 0.7600"


def test_special_alert_requires_both_complete_windows() -> None:
    assert is_special_alert({"p30": 90.0, "p180": 95.0}, 90)
    assert not is_special_alert({"p30": 89.9, "p180": 95.0}, 90)
    assert not is_special_alert({"p30": 95.0, "p180": None}, 90)


def test_ntfy_target_accepts_topic_or_full_https_url() -> None:
    assert resolve_ntfy_target("private-topic", "NTFY_DAILY_URL") == ("https://ntfy.sh/", "private-topic")
    assert resolve_ntfy_target("https://example.com/private-topic", "NTFY_DAILY_URL") == ("https://example.com/", "private-topic")
    with pytest.raises(NotificationError, match="topic 名或完整"):
        resolve_ntfy_target("http://ntfy.sh/private", "NTFY_DAILY_URL")


def test_post_ntfy_uses_utf8_json(monkeypatch) -> None:
    captured = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("src.notifier.requests.post", fake_post)
    post_ntfy("daily-topic", "Steam 挂刀指数日报", "I5 = 0.7000", 3)
    assert captured["url"] == "https://ntfy.sh/"
    assert captured["json"]["topic"] == "daily-topic"
    assert captured["json"]["title"] == "Steam 挂刀指数日报"
