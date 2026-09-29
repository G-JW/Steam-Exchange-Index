from __future__ import annotations

from urllib.parse import urlparse
import re

import requests

class NotificationError(RuntimeError):
    pass


def format_message(indexes: dict[float, float]) -> str:
    return "\n".join([
        f"I5 = {indexes[0.05]:.4f}",
        f"I10 = {indexes[0.10]:.4f}",
        f"I20 = {indexes[0.20]:.4f}",
    ])


def is_special_alert(stats: dict[str, float | None], threshold: float) -> bool:
    return all(stats.get(key) is not None and float(stats[key]) >= threshold for key in ("p30", "p180"))


def resolve_ntfy_target(value: str, variable_name: str) -> tuple[str, str]:
    value = value.strip()
    if re.fullmatch(r"[-_A-Za-z0-9]{1,64}", value):
        return "https://ntfy.sh/", value
    parsed = urlparse(value)
    topic = parsed.path.strip("/")
    if parsed.scheme != "https" or not parsed.netloc or not re.fullmatch(r"[-_A-Za-z0-9]{1,64}", topic):
        raise NotificationError(f"环境变量 {variable_name} 必须是 ntfy topic 名或完整的 https:// topic URL")
    return f"{parsed.scheme}://{parsed.netloc}/", topic


def post_ntfy(url: str, title: str, message: str, priority: int, timeout: float = 15) -> None:
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
        # A topic URL may itself be secret; do not include the request
        # exception text because requests commonly embeds the full URL in it.
        raise NotificationError(f"ntfy 发送失败（{type(exc).__name__}）") from exc
