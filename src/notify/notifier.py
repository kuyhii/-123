"""
src/notify/notifier.py - 通知器

支持:
- 控制台(rich + 颜色,默认)
- Telegram(可选,需 .env 配 BOT_TOKEN / CHAT_ID)
- 写日志文件(用于审计)

事件类型:
- 信号:策略产生新信号
- 成交:订单成交
- 警告:风控熔断 / 日内亏损告警
- 错误:网络错误 / API 错误
- 启动/停止:系统生命周期
"""
import sys
import json
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from pathlib import Path

# 让 `python src/notify/notifier.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import PROJECT_ROOT, CONFIG
from src.logger import get_logger

log = get_logger("notify")


class Severity(str, Enum):
    INFO = "INFO"
    SIGNAL = "SIGNAL"
    TRADE = "TRADE"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass
class NotifyEvent:
    severity: Severity
    title: str
    body: str = ""
    metadata: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def render(self) -> str:
        icons = {
            Severity.INFO: "ℹ️ ",
            Severity.SIGNAL: "📡",
            Severity.TRADE: "💰",
            Severity.WARN: "⚠️ ",
            Severity.ERROR: "❌",
        }
        icon = icons.get(self.severity, "·")
        ts_str = time.strftime("%H:%M:%S", time.localtime(self.ts))
        return f"{icon} [{ts_str}] {self.title}\n   {self.body}" if self.body else f"{icon} [{ts_str}] {self.title}"


class Notifier:
    """
    多通道通知器

    用法:
        n = Notifier()
        n.info("启动", "量化系统已上线")
        n.signal("BTCUSDT", "BUY", "金叉信号")
        n.warn("风控熔断", "日内亏损 12%")
        n.error("API 错误", "rate limit")
    """

    def __init__(self,
                 console: bool = True,
                 telegram: bool = False,
                 file_log: bool = True):
        """
        Args:
            console:  是否打印到终端
            telegram: 是否启用 Telegram(需 .env 配)
            file_log: 是否写通知日志到 logs/notifications.log
        """
        self.console_enabled = console
        self.telegram_enabled = telegram
        self.file_log_enabled = file_log

        # 加载 Telegram 配置
        self.tg_token = CONFIG.binance.api_key if False else None  # 下面用专门字段
        # 从环境变量读(独立于 binance key)
        import os
        self.tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        # 实际是否启用
        if telegram and not (self.tg_token and self.tg_chat_id):
            log.warning("Telegram 未配置(token / chat_id 缺失),自动关闭")
            self.telegram_enabled = False

        # 文件日志
        if file_log:
            self.log_path = PROJECT_ROOT / "logs" / "notifications.log"
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # 限流:同事件 1 分钟内不重复发
        self._last_sent: dict = {}

    def _send(self, event: NotifyEvent):
        """统一发送"""
        # 限流
        key = f"{event.severity}:{event.title}"
        now = time.time()
        if key in self._last_sent and now - self._last_sent[key] < 60:
            return
        self._last_sent[key] = now

        text = event.render()
        if self.console_enabled:
            print(f"\n{text}")
        if self.telegram_enabled:
            self._send_telegram(event.render())
        if self.file_log_enabled:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
            except Exception as e:
                log.debug(f"写通知日志失败: {e}")

    def _send_telegram(self, text: str):
        """发送 Telegram(失败不抛异常)"""
        try:
            url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": self.tg_chat_id,
                "text": text[:3500],  # TG 限制 4096
                "parse_mode": "HTML",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            log.debug(f"Telegram 发送失败: {e}")

    # ==================== 便捷方法 ====================

    def info(self, title: str, body: str = "", **meta):
        self._send(NotifyEvent(Severity.INFO, title, body, meta))

    def signal(self, symbol: str, side: str, reason: str = ""):
        title = f"信号: {symbol} {side}"
        self._send(NotifyEvent(Severity.SIGNAL, title, reason,
                                {"symbol": symbol, "side": side}))

    def trade(self, symbol: str, side: str, qty: float, price: float):
        body = f"{qty} @ {price}"
        self._send(NotifyEvent(Severity.TRADE,
                                f"成交: {side} {symbol}", body,
                                {"symbol": symbol, "side": side,
                                 "qty": qty, "price": price}))

    def warn(self, title: str, body: str = "", **meta):
        self._send(NotifyEvent(Severity.WARN, title, body, meta))

    def error(self, title: str, body: str = "", **meta):
        self._send(NotifyEvent(Severity.ERROR, title, body, meta))


# ==================== 全局单例 ====================
DEFAULT_NOTIFIER = Notifier()


# ==================== 单独测试 ====================
if __name__ == "__main__":
    n = Notifier(console=True, telegram=False, file_log=True)
    print("🔔 通知器测试\n")
    n.info("系统启动", "v0.6 测试通知")
    n.signal("BTCUSDT", "BUY", "金叉信号")
    n.trade("BTCUSDT", "BUY", 0.001, 60000)
    n.warn("风控告警", "日内亏损 12%")
    n.error("API 错误", "rate limit exceeded")
    print("\n📁 日志写入 logs/notifications.log")
