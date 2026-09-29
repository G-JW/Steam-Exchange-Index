from __future__ import annotations

import re
from urllib.parse import urlparse

import requests


class NotificationError(RuntimeError):
    """ntfy 目标无效或通知请求失败。"""

    pass


def format_message(indexes: dict[float, float]) -> str:
    """通知正文只保留三个客观指数。"""

    return "\n".join([
        f"I5 = {indexes[0.05]:.4f}",
        f"I10 = {indexes[0.10]:.4f}",
        f"I20 = {indexes[0.20]:.4f}",
    ])


def is_special_alert(stats: dict[str, float | None], threshold: float) -> bool:
    """30 日和 180 日历史位置同时达标才触发特别提醒。"""

    return all(stats.get(key) is not None and float(stats[key]) >= threshold for key in ("p30", "p180"))


def resolve_ntfy_target(value: str, variable_name: str) -> tuple[str, str]:
    """把 topic 名或完整 HTTPS URL 解析成 ntfy 根地址与 topic。"""

    value = value.strip()
    if re.fullmatch(r"[-_A-Za-z0-9]{1,64}", value):
        return "https://ntfy.sh/", value
    parsed = urlparse(value)
    topic = parsed.path.strip("/")
    if parsed.scheme != "https" or not parsed.netloc or not re.fullmatch(r"[-_A-Za-z0-9]{1,64}", topic):
        raise NotificationError(f"环境变量 {variable_name} 必须是 ntfy topic 名或完整的 https:// topic URL")
    return f"{parsed.scheme}://{parsed.netloc}/", topic


def post_ntfy(url: str, title: str, message: str, priority: int, timeout: float = 15) -> None:
    """使用 ntfy JSON API 发送 UTF-8 通知。"""

    root_url, topic = resolve_ntfy_target(url, "ntfy target")
    try:
        response = requests.post(
            root_url,
            json={
                "topic": topic,
                "title": title,
                "message": message,
                "priority": priority,
                "tags": ["chart_with_upwards_trend"],
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # Topic URL 可能包含私密 topic；requests 的异常常带完整 URL，不能直接记录。
        raise NotificationError(f"ntfy 发送失败（{type(exc).__name__}）") from exc
