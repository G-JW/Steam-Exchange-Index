from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.calculator import CalculationError, calculate_indexes, top_items
from src.collector import CollectionError, fetch_items
from src.config import ConfigError, load_config
from src.filters import enrich_and_filter
from src.history import calculate_statistics, load_history, make_history_row, upsert_history
from src.notifier import NotificationError, format_message, load_state, post_ntfy, save_state, select_level, should_notify


ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / "data" / "index_history.csv"
STATE_PATH = ROOT / "data" / "notification_state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Steam 挂刀指数监控")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"), help="配置文件路径")
    return parser.parse_args()


def print_summary(indexes: dict[float, float], valid_count: int, minimum: float, stats: dict, candidates: list) -> None:
    print("\n=== Steam 挂刀指数 ===")
    for percentile, value in indexes.items():
        print(f"I{int(percentile * 100)}: {value:.4f}")
    print(f"有效饰品: {valid_count}")
    print(f"最低挂刀比例: {minimum:.4f}")
    for key in ("ma7", "ma30", "p30", "p90", "p365"):
        if stats.get(key) is not None:
            suffix = "%" if key.startswith("p") else ""
            print(f"{key.upper()}: {stats[key]:.4f}{suffix}")
    if candidates:
        print("\nTop 挂刀候选:")
        for number, item in enumerate(candidates, start=1):
            print(f"{number:2}. {item.name} | ratio={item.ratio:.4f} | {item.best_platform}={item.best_platform_price:.2f} | Steam买价={item.steam_buy_price:.2f} | 今日成交={item.today_volume:g}")


def run() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        token = os.environ.get("CSQAQ_API_TOKEN", "").strip()
        if not token:
            raise ConfigError("缺少环境变量 CSQAQ_API_TOKEN")
        run_time = datetime.now(ZoneInfo("Asia/Shanghai"))
        items, _ = fetch_items(config, token)
        valid, skipped = enrich_and_filter(items, config)
        minimum_required = int(config["index"]["min_valid_items"])
        logging.info("Valid items: %d; skipped by validation/filters: %d", len(valid), skipped)
        if len(valid) < minimum_required:
            raise CalculationError(f"有效饰品仅 {len(valid)} 件，低于要求的 {minimum_required} 件")
        percentiles = [float(value) for value in config["index"]["percentiles"]]
        indexes = calculate_indexes(valid, percentiles)
        primary = float(config["index"]["primary"])
        minimum = min(float(item.ratio) for item in valid)
        history = load_history(HISTORY_PATH)
        stats = calculate_statistics(
            history,
            run_time.date().isoformat(),
            indexes[primary],
            config["history"]["moving_averages"],
            config["history"]["percentile_windows"],
        )
        candidates = top_items(valid, int(config["top_items"]["count"])) if config["top_items"]["enabled"] else []
        upsert_history(HISTORY_PATH, make_history_row(run_time, indexes, len(valid), minimum, stats))
        print_summary(indexes, len(valid), minimum, stats, candidates)

        notification = config["notification"]
        if not notification["enabled"]:
            return 0
        level = select_level(indexes[primary], notification["thresholds"])
        title = "Steam 挂刀指数日报"
        priority = int(notification.get("default_priority", 3))
        send = bool(notification["daily_report"])
        threshold_send = False
        level_rank = 0
        if level:
            level_rank, threshold = level
            threshold_send = True
            cooldown = notification["cooldown"]
            if cooldown["enabled"]:
                threshold_send = should_notify(
                    run_time.date(),
                    level_rank,
                    load_state(STATE_PATH),
                    int(cooldown["days"]),
                    bool(notification["notify_on_level_upgrade"]),
                )
            if threshold_send:
                title = f"Steam 挂刀指数 · {threshold['label']}"
                priority = int(threshold["priority"])
                send = True
        if not send:
            logging.info("通知条件未满足或处于冷却期，跳过 ntfy")
            return 0
        ntfy_url = os.environ.get("NTFY_URL", "").strip()
        if not ntfy_url:
            raise NotificationError("需要发送通知，但缺少环境变量 NTFY_URL")
        post_ntfy(ntfy_url, title, format_message(run_time.date(), indexes, len(valid), stats, candidates), priority)
        if threshold_send:
            save_state(STATE_PATH, {"last_notification_date": run_time.date().isoformat(), "last_level": level_rank, "last_index": indexes[primary]})
        logging.info("ntfy 通知发送成功")
        return 0
    except (ConfigError, CollectionError, CalculationError, ValueError) as exc:
        logging.error("任务失败: %s", exc)
        return 1
    except NotificationError as exc:
        logging.error("指数已保存，但%s", exc)
        return 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run())
