from __future__ import annotations

import logging
import time
from typing import Any

import requests

from .models import MarketItem, optional_float


class CollectionError(RuntimeError):
    pass


def normalize_item(raw: dict[str, Any]) -> MarketItem | None:
    if not isinstance(raw, dict):
        return None
    item_id = raw.get("id")
    name = raw.get("name") or raw.get("market_hash_name")
    if item_id is None or not isinstance(name, str) or not name.strip():
        return None
    return MarketItem(
        item_id=str(item_id),
        name=name.strip(),
        steam_buy_price=optional_float(raw.get("steam_buy_price")),
        steam_buy_num=optional_float(raw.get("steam_buy_num")),
        today_volume=optional_float(raw.get("turnover_number")),
        buff_sell_price=optional_float(raw.get("buff_sell_price")),
        buff_sell_num=optional_float(raw.get("buff_sell_num")),
        yyyp_sell_price=optional_float(raw.get("yyyp_sell_price")),
        yyyp_sell_num=optional_float(raw.get("yyyp_sell_num")),
    )


def _request_page(session: requests.Session, endpoint: str, token: str, payload: dict[str, Any], timeout: float, retries: int) -> list[Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.post(
                endpoint,
                headers={"ApiToken": token, "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or body.get("code") != 200 or not isinstance(body.get("data"), list):
                message = body.get("msg") if isinstance(body, dict) else "非对象响应"
                raise CollectionError(f"CSQAQ 返回结构异常: {message}")
            return body["data"]
        except (requests.RequestException, ValueError, CollectionError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 4))
    raise CollectionError(f"CSQAQ 请求失败（已重试 {retries} 次）: {last_error}")


def bind_local_ip(session: requests.Session, endpoint: str, token: str, timeout: float) -> None:
    """Bind the caller's current public IP before authenticated data requests.

    CSQAQ limits this endpoint to one request every 30 seconds, so this is
    intentionally a single request rather than using the normal retry loop.
    """
    try:
        response = session.post(
            endpoint,
            headers={"ApiToken": token},
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CollectionError(f"CSQAQ 白名单 IP 绑定请求失败: {type(exc).__name__}") from exc
    if not isinstance(body, dict) or body.get("code") != 200:
        message = body.get("msg") if isinstance(body, dict) else "非对象响应"
        raise CollectionError(f"CSQAQ 白名单 IP 绑定失败: {message}")
    logging.info("CSQAQ 白名单 IP 绑定成功")


def fetch_items(config: dict[str, Any], token: str, session: requests.Session | None = None) -> tuple[list[MarketItem], dict[str, int]]:
    source = config["data_source"]
    platforms = [platform for platform in ("BUFF", "YYYP") if platform in config["platforms"]]
    volume = config["filters"]["volume"]
    payload_base: dict[str, Any] = {
        "res": 0,
        "platforms": "-".join(platforms),
        "sort_by": 1,
    }
    if volume["enabled"]:
        payload_base["turnover"] = volume["min_today_volume"]
    client = session or requests.Session()
    if source["bind_local_ip"]:
        bind_local_ip(
            client,
            source["bind_ip_endpoint"],
            token,
            float(source["request_timeout_seconds"]),
        )
    raw_count = parsed_count = skipped_count = 0
    items: list[MarketItem] = []
    for page in range(1, int(source["max_pages"]) + 1):
        payload = {**payload_base, "page_index": page}
        rows = _request_page(
            client,
            source["endpoint"],
            token,
            payload,
            float(source["request_timeout_seconds"]),
            int(source["retries"]),
        )
        if not rows:
            break
        raw_count += len(rows)
        for row in rows:
            item = normalize_item(row)
            if item is None:
                skipped_count += 1
            else:
                items.append(item)
                parsed_count += 1
    else:
        raise CollectionError(f"达到 max_pages={source['max_pages']} 仍有数据，拒绝使用可能不完整的结果")
    if raw_count == 0:
        raise CollectionError("CSQAQ 未返回任何饰品数据")
    logging.info("Fetched items: %d; parsed: %d; skipped malformed: %d", raw_count, parsed_count, skipped_count)
    return items, {"fetched": raw_count, "parsed": parsed_count, "skipped_malformed": skipped_count}
