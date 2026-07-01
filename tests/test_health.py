"""
tests/test_health.py - 健康检查测试
"""
import pytest
import time
from src.utils.health import HealthMonitor, HealthStatus


class TestHealthMonitor:
    def setup_method(self):
        # 重置单例
        HealthMonitor._instance = None

    def test_register_and_success(self):
        h = HealthMonitor.get()
        h.register("test")
        h.record_success("test")
        c = h.components["test"]
        assert c.status == HealthStatus.HEALTHY
        assert c.success_count == 1
        assert c.error_count == 0

    def test_errors_degrade(self):
        h = HealthMonitor.get()
        h.register("test")
        for i in range(3):
            h.record_error("test", f"err {i}")
        c = h.components["test"]
        assert c.status == HealthStatus.DEGRADED
        assert c.error_count == 3

    def test_5_errors_unhealthy(self):
        h = HealthMonitor.get()
        h.register("test")
        for i in range(5):
            h.record_error("test", f"err {i}")
        c = h.components["test"]
        assert c.status == HealthStatus.UNHEALTHY

    def test_recovery(self):
        h = HealthMonitor.get()
        h.register("test")
        h.record_error("test", "boom")
        h.record_success("test")
        c = h.components["test"]
        assert c.status == HealthStatus.HEALTHY
        assert c.error_count == 1
        assert c.success_count == 1

    def test_stale_detection(self):
        h = HealthMonitor.get()
        h.register("test")
        h.record_success("test")
        # 手动把时间改到很久以前
        h.components["test"].last_success_ts = time.time() - 1000
        assert h.components["test"].is_stale(max_age_sec=60)

    def test_is_healthy_no_components(self):
        h = HealthMonitor.get()
        assert h.is_healthy()  # 没组件时算健康

    def test_snapshot(self):
        h = HealthMonitor.get()
        h.register("a")
        h.register("b")
        h.record_success("a")
        h.record_error("b", "fail")
        snap = h.snapshot()
        assert "uptime_sec" in snap
        assert "overall" in snap
        assert "a" in snap["components"]
        assert "b" in snap["components"]
        assert snap["components"]["a"]["status"] == "HEALTHY"
        assert snap["components"]["b"]["status"] == "DEGRADED"
