"""
src/strategy/base.py - 策略基类

所有自定义策略继承 Strategy,实现 on_kline / on_kline_closed。
"""
from abc import ABC, abstractmethod
from typing import Optional, List

from src.data.models import Kline, Signal


class Strategy(ABC):
    """策略基类"""

    name: str = "Unnamed"

    def __init__(self, **params):
        self.params = params
        self.klines: List[Kline] = []
        self.signals: List[Signal] = []

    async def on_init(self) -> None:
        """策略启动钩子"""
        pass

    async def on_stop(self) -> None:
        """策略停止钩子"""
        pass

    @abstractmethod
    def on_kline_closed(self, kline: Kline) -> Optional[Signal]:
        """
        K 线收盘时调用,返回 Signal 或 None
        """
        pass

    def on_kline_update(self, kline: Kline) -> Optional[Signal]:
        """K 线更新中调用(可选覆盖,默认 no-op)"""
        return None

    def feed(self, kline: Kline, closed: bool = False) -> Optional[Signal]:
        """外部喂数据入口"""
        self.klines.append(kline)
        if closed:
            sig = self.on_kline_closed(kline)
            if sig:
                self.signals.append(sig)
            return sig
        return self.on_kline_update(kline)
