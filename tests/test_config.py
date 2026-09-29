from __future__ import annotations

import copy

import pytest

from src.config import ConfigError, validate_config


def test_invalid_net_rate_rejected(config: dict) -> None:
    bad = copy.deepcopy(config)
    bad["steam"]["net_rate"] = 0
    with pytest.raises(ConfigError, match="net_rate"):
        validate_config(bad)


def test_required_indexes_cannot_be_removed(config: dict) -> None:
    bad = copy.deepcopy(config)
    bad["index"]["percentiles"] = [0.10]
    with pytest.raises(ConfigError, match="至少包含"):
        validate_config(bad)


def test_duplicate_platforms_rejected(config: dict) -> None:
    bad = copy.deepcopy(config)
    bad["platforms"] = ["BUFF", "BUFF"]
    with pytest.raises(ConfigError, match="platforms"):
        validate_config(bad)


def test_bind_endpoint_must_use_https(config: dict) -> None:
    bad = copy.deepcopy(config)
    bad["data_source"]["bind_ip_endpoint"] = "http://example.invalid"
    with pytest.raises(ConfigError, match="bind_ip_endpoint"):
        validate_config(bad)


def test_special_notification_requires_both_history_windows(config: dict) -> None:
    bad = copy.deepcopy(config)
    bad["history"]["percentile_windows"] = [30]
    with pytest.raises(ConfigError, match="30 和 180"):
        validate_config(bad)
