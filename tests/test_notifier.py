"""
tests/test_notifier.py - 通知器测试
"""
import pytest
import time
from src.notify.notifier import Notifier, NotifyEvent, Severity


class TestNotifier:
    def test_event_render(self):
        e = NotifyEvent(Severity.SIGNAL, "BTCUSDT BUY", "金叉信号")
        text = e.render()
        assert "BTCUSDT BUY" in text
        assert "金叉信号" in text
        assert "📡" in text  # SIGNAL icon

    def test_render_no_body(self):
        e = NotifyEvent(Severity.INFO, "启动")
        text = e.render()
        assert "启动" in text
        assert "ℹ️" in text

    def test_rate_limit(self):
        """同事件 1 分钟内只发一次"""
        n = Notifier(console=False, telegram=False, file_log=False)
        event = NotifyEvent(Severity.WARN, "测试限流", "")
        n._send(event)
        n._send(event)  # 第二次应被限流
        # severity 是枚举对象,key 包含 "Severity.WARN"
        assert any("测试限流" in k for k in n._last_sent)

    def test_console_disabled(self, capsys):
        n = Notifier(console=True, telegram=False, file_log=False)
        n.info("测试输出", "内容")
        captured = capsys.readouterr()
        assert "测试输出" in captured.out

    def test_severity_enum(self):
        assert Severity.INFO.value == "INFO"
        assert Severity.SIGNAL.value == "SIGNAL"
        assert Severity.TRADE.value == "TRADE"
        assert Severity.WARN.value == "WARN"
        assert Severity.ERROR.value == "ERROR"

    def test_metadata(self):
        e = NotifyEvent(Severity.TRADE, "成交", "BTCUSDT", {"qty": 0.001, "price": 60000})
        assert e.metadata["qty"] == 0.001
        assert e.metadata["price"] == 60000
