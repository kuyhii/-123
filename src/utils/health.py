"""
src/utils/health.py - 健康检查

监控:
- 进程存活
- 关键模块状态
- 最近一次成功时间
- 错误计数
"""
import sys
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
from pathlib import Path

# 让 `python src/utils/health.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.logger import get_logger

log = get_logger("health")


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus = HealthStatus.HEALTHY
    last_success_ts: float = 0.0
    last_error: str = ""
    error_count: int = 0
    success_count: int = 0
    metadata: dict = field(default_factory=dict)

    def is_stale(self, max_age_sec: float = 60.0) -> bool:
        """长时间无成功 → 视为不健康"""
        if self.last_success_ts == 0:
            return True
        return (time.time() - self.last_success_ts) > max_age_sec


class HealthMonitor:
    """
    全局健康监控

    用法:
        h = HealthMonitor.get()
        h.register("kline_ws")
        h.record_success("kline_ws")
        h.record_error("kline_ws", "ConnectionError")

        if not h.is_healthy():
            ...
    """
    _instance: Optional["HealthMonitor"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.components: Dict[str, ComponentHealth] = {}
        self.started_at = time.time()

    @classmethod
    def get(cls) -> "HealthMonitor":
        """单例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def register(self, name: str, **metadata):
        """注册一个组件"""
        if name not in self.components:
            self.components[name] = ComponentHealth(name=name, metadata=metadata)
            log.info(f"注册组件: {name}")

    def record_success(self, name: str):
        """记录一次成功"""
        if name not in self.components:
            self.register(name)
        c = self.components[name]
        c.last_success_ts = time.time()
        c.success_count += 1
        if c.status != HealthStatus.HEALTHY:
            log.info(f"组件恢复: {name}")
        c.status = HealthStatus.HEALTHY

    def record_error(self, name: str, error: str = ""):
        """记录一次错误"""
        if name not in self.components:
            self.register(name)
        c = self.components[name]
        c.error_count += 1
        c.last_error = error
        c.status = HealthStatus.DEGRADED if c.error_count < 5 else HealthStatus.UNHEALTHY

    def is_healthy(self) -> bool:
        """整体是否健康"""
        for c in self.components.values():
            if c.status == HealthStatus.UNHEALTHY:
                return False
            if c.is_stale():
                return False
        return True

    def snapshot(self) -> dict:
        """当前状态快照"""
        return {
            "uptime_sec": time.time() - self.started_at,
            "overall": HealthStatus.HEALTHY.value if self.is_healthy() else HealthStatus.UNHEALTHY.value,
            "components": {
                name: {
                    "status": c.status.value,
                    "success_count": c.success_count,
                    "error_count": c.error_count,
                    "last_success_ts": c.last_success_ts,
                    "last_error": c.last_error,
                    "stale": c.is_stale(),
                }
                for name, c in self.components.items()
            }
        }

    def pretty(self) -> str:
        """人类可读输出"""
        snap = self.snapshot()
        out = [f"系统状态: {snap['overall']}  |  运行时长: {snap['uptime_sec']:.0f}s\n"]
        for name, c in snap["components"].items():
            icon = {"HEALTHY": "✅", "DEGRADED": "⚠️ ", "UNHEALTHY": "❌"}.get(c["status"], "?")
            out.append(
                f"  {icon} {name:<20} status={c['status']:<10} "
                f"成功={c['success_count']:<5} 失败={c['error_count']:<3}"
            )
            if c["last_error"]:
                out.append(f"      最近错误: {c['last_error']}")
        return "\n".join(out)


# ==================== 单独测试 ====================
if __name__ == "__main__":
    h = HealthMonitor.get()
    h.register("kline_ws")
    h.register("user_data_ws")
    h.register("scheduler")

    h.record_success("kline_ws")
    h.record_success("user_data_ws")
    h.record_error("scheduler", "API timeout")

    print(h.pretty())
    print(f"\n整体健康: {h.is_healthy()}")
