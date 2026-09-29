from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


def _require(mapping: dict[str, Any], path: str, expected: type) -> Any:
    current: Any = mapping
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ConfigError(f"缺少配置项: {path}")
        current = current[part]
    if expected is float:
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise ConfigError(f"配置项 {path} 必须是数字")
    elif not isinstance(current, expected):
        raise ConfigError(f"配置项 {path} 必须是 {expected.__name__}")
    return current


def load_config(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件不存在: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML 解析失败: {exc}") from exc
    if not isinstance(config, dict):
        raise ConfigError("配置文件顶层必须是对象")
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    if _require(config, "data_source.provider", str) != "csqaq":
        raise ConfigError("data_source.provider 目前只支持 csqaq")
    endpoint = _require(config, "data_source.endpoint", str)
    if not endpoint.startswith("https://"):
        raise ConfigError("data_source.endpoint 必须使用 https://")
    _require(config, "data_source.bind_local_ip", bool)
    bind_endpoint = _require(config, "data_source.bind_ip_endpoint", str)
    if not bind_endpoint.startswith("https://"):
        raise ConfigError("data_source.bind_ip_endpoint 必须使用 https://")
    for path in ("data_source.request_timeout_seconds", "data_source.retries", "data_source.max_pages"):
        if _require(config, path, float) <= 0:
            raise ConfigError(f"配置项 {path} 必须大于 0")
    platforms = _require(config, "platforms", list)
    if not platforms or len(platforms) != len(set(platforms)) or not set(platforms).issubset({"BUFF", "YYYP"}):
        raise ConfigError("platforms 必须是 BUFF/YYYP 的非空列表")
    net_rate = float(_require(config, "steam.net_rate", float))
    if not 0 < net_rate <= 1:
        raise ConfigError("steam.net_rate 必须在 (0, 1] 内")
    for section in ("volume", "price", "ratio", "steam_buy_orders", "platform_sell_orders"):
        _require(config, f"filters.{section}.enabled", bool)
    if float(_require(config, "filters.volume.min_today_volume", float)) < 0:
        raise ConfigError("成交量阈值不能为负数")
    for section in ("price", "ratio"):
        low = float(_require(config, f"filters.{section}.min", float))
        high = float(_require(config, f"filters.{section}.max", float))
        if low < 0 or high <= low:
            raise ConfigError(f"filters.{section} 的 min/max 无效")
    for section in ("steam_buy_orders", "platform_sell_orders"):
        if float(_require(config, f"filters.{section}.min", float)) < 0:
            raise ConfigError(f"filters.{section}.min 不能为负数")
    percentiles = _require(config, "index.percentiles", list)
    if not percentiles or any(isinstance(q, bool) or not isinstance(q, (int, float)) or not 0 < q <= 1 for q in percentiles):
        raise ConfigError("index.percentiles 必须是 (0, 1] 内的数字列表")
    if not {0.05, 0.10, 0.20}.issubset({float(q) for q in percentiles}):
        raise ConfigError("index.percentiles 必须至少包含 0.05、0.10、0.20")
    primary = float(_require(config, "index.primary", float))
    if primary not in [float(q) for q in percentiles]:
        raise ConfigError("index.primary 必须包含在 index.percentiles 中")
    if _require(config, "index.market_value_platform", str) != "BUFF":
        raise ConfigError("首版 index.market_value_platform 必须为 BUFF")
    if _require(config, "index.min_valid_items", float) <= 0:
        raise ConfigError("index.min_valid_items 必须大于 0")
    for path in ("history.moving_averages", "history.percentile_windows"):
        values = _require(config, path, list)
        if not values or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in values):
            raise ConfigError(f"{path} 必须是正整数列表")
    _require(config, "notification.enabled", bool)
    if _require(config, "notification.provider", str) != "ntfy":
        raise ConfigError("notification.provider 目前只支持 ntfy")
    special_percentile = float(_require(config, "notification.special_percentile", float))
    if not 0 < special_percentile <= 100:
        raise ConfigError("notification.special_percentile 必须在 (0, 100] 内")
    if not {30, 180}.issubset(set(config["history"]["percentile_windows"])):
        raise ConfigError("特别提醒需要 history.percentile_windows 包含 30 和 180")
    _require(config, "top_items.enabled", bool)
    if _require(config, "top_items.count", float) < 0:
        raise ConfigError("top_items.count 不能为负数")
