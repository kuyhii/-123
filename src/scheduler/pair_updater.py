"""
src/scheduler/pair_updater.py - 交易对池定时更新

启动后,后台运行一个调度线程,每天 00:00 UTC(北京时间 8:00)刷新交易对池。
可以独立运行,也可以集成进主程序。
"""
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# 让 `python src/scheduler/pair_updater.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import CONFIG
from src.logger import get_logger
from src.strategy.trading_pairs import refresh_pairs, load_pairs, get_diff_report

log = get_logger("pair_updater")


def _seconds_until_next(target_hour_utc: int, target_minute_utc: int = 0) -> float:
    """
    计算距离下一次目标时刻的秒数。
    例: 现在 14:32 UTC, 目标 00:00 UTC → 9小时28分
        现在 23:59 UTC, 目标 00:00 UTC → 1分钟
    """
    now = datetime.now(timezone.utc)
    target = now.replace(hour=target_hour_utc, minute=target_minute_utc, second=0, microsecond=0)
    if target <= now:
        # 今天的已过,等明天的
        target = target + timedelta(days=1)
    delta = (target - now).total_seconds()
    return delta


def _parse_time(s: str) -> tuple:
    """解析 'HH:MM' 字符串为 (hour, minute)"""
    try:
        parts = s.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError
        return h, m
    except Exception:
        log.warning(f"无法解析 PAIR_UPDATE_TIME={s!r},使用默认 00:00 UTC")
        return 0, 0


def run_once(top_n: Optional[int] = None) -> bool:
    """执行一次更新。返回是否成功"""
    log.info("⏰ 计划任务:刷新交易对池")
    try:
        old = load_pairs()
        new = refresh_pairs(top_n)
        if not new:
            log.error("刷新失败,池子未更新")
            return False
        diff = get_diff_report(old, new)
        if diff["added"] or diff["removed"]:
            log.info(
                f"池子变化: ➕ {len(diff['added'])}  ➖ {len(diff['removed'])}  "
                f"✓ {len(diff['kept'])} 保留"
            )
            if diff["added"]:
                log.info(f"  新增: {', '.join(diff['added'])}")
            if diff["removed"]:
                log.info(f"  剔除: {', '.join(diff['removed'])}")
        else:
            log.info("池子无变化")
        return True
    except Exception as e:
        log.error(f"更新失败: {e}")
        return False


def run_forever():
    """
    后台守护线程,每天 00:00 UTC 刷新。
    Ctrl+C 退出。
    """
    hour, minute = _parse_time(CONFIG.pool.update_time_utc)
    log.info(f"🕐 启动调度器:每天 {hour:02d}:{minute:02d} UTC 更新交易对池")

    while True:
        secs = _seconds_until_next(hour, minute)
        # 下次执行时间
        next_run = datetime.now(timezone.utc) + timedelta(seconds=secs)
        log.info(f"   下次执行: {next_run.isoformat()} (等待 {secs/3600:.1f} 小时)")

        # 分段 sleep,便于响应 Ctrl+C
        end_time = time.time() + secs
        while time.time() < end_time:
            remaining = end_time - time.time()
            time.sleep(min(60, remaining))

        # 到点了,执行
        run_once()


def run_forever_async(stop_event: Optional[threading.Event] = None):
    """线程入口,支持外部 stop 事件"""
    hour, minute = _parse_time(CONFIG.pool.update_time_utc)
    log.info(f"🕐 调度线程启动:每天 {hour:02d}:{minute:02d} UTC")

    while True:
        if stop_event and stop_event.is_set():
            log.info("调度线程收到停止信号")
            return
        secs = _seconds_until_next(hour, minute)
        # 分段 sleep
        end_time = time.time() + secs
        while time.time() < end_time:
            if stop_event and stop_event.is_set():
                return
            remaining = end_time - time.time()
            time.sleep(min(60, remaining))

        run_once()


# ==================== 单独运行 ====================

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="交易对池调度器")
    p.add_argument("--once", action="store_true", help="只跑一次就退出")
    p.add_argument("--daemon", action="store_true", help="持续后台运行(每天 00:00 UTC)")
    args = p.parse_args()

    if args.once:
        ok = run_once()
        sys.exit(0 if ok else 1)
    elif args.daemon:
        try:
            run_forever()
        except KeyboardInterrupt:
            log.info("调度器退出")
    else:
        p.print_help()
