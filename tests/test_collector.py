from __future__ import annotations

import pytest
import requests

from src.collector import CollectionError, _request_page, bind_local_ip, fetch_items, normalize_item


class Response:
    def __init__(self, body=None, error=None):
        self.body = body
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.body


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)

    def post(self, *args, **kwargs):
        return next(self.responses)


def test_normalize_real_schema() -> None:
    item = normalize_item({"id": 1, "name": "饰品", "steam_buy_price": 5.25, "steam_buy_num": 10, "turnover_number": 101, "buff_sell_price": 3.5, "buff_sell_num": 278, "yyyp_sell_price": 4.18, "yyyp_sell_num": 20})
    assert item is not None
    assert item.today_volume == 101
    assert item.buff_sell_num == 278


def test_request_failure_retries_then_fails(monkeypatch) -> None:
    monkeypatch.setattr("src.collector.time.sleep", lambda _: None)
    error = requests.ConnectionError("offline")
    session = Session([Response(error=error), Response(error=error)])
    with pytest.raises(CollectionError, match="已重试 2 次"):
        _request_page(session, "https://example.invalid", "secret", {}, 1, 2)


def test_unexpected_response_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr("src.collector.time.sleep", lambda _: None)
    session = Session([Response({"code": 200, "data": {}})])
    with pytest.raises(CollectionError, match="结构异常"):
        _request_page(session, "https://example.invalid", "secret", {}, 1, 1)


def test_platform_order_is_normalized_for_api(config: dict) -> None:
    config["platforms"] = ["YYYP", "BUFF"]
    session = Session([
        Response({"code": 200, "msg": "Success", "data": "bound"}),
        Response({"code": 200, "data": [{"id": 1, "name": "A"}]}),
        Response({"code": 200, "data": []}),
    ])
    items, counts = fetch_items(config, "secret", session=session)
    assert len(items) == 1
    assert counts["fetched"] == 1


def test_bind_local_ip_rejects_business_error() -> None:
    session = Session([Response({"code": 401, "msg": "not allowed", "data": ""})])
    with pytest.raises(CollectionError, match="not allowed"):
        bind_local_ip(session, "https://example.invalid/bind", "secret", 1)
