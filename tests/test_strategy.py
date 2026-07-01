"""
tests/test_strategy.py - 策略测试
"""
import pytest
from src.strategy.examples.dual_ma import DualMAStrategy
from src.strategy.base import Strategy
from src.data.models import Kline, Signal, Side


def make_klines(closes, symbol="TESTUSDT"):
    return [
        Kline(
            open_time=i * 60000, open=c, high=c + 0.5, low=c - 0.5, close=c,
            volume=100, close_time=(i + 1) * 60000, symbol=symbol
        )
        for i, c in enumerate(closes)
    ]


class TestDualMA:
    def test_strategy_is_abstract_base(self):
        assert issubclass(DualMAStrategy, Strategy)

    def test_name(self):
        assert DualMAStrategy.name == "DualMA"

    def test_uptrend_generates_buy(self):
        """单边上涨 → 金叉 → BUY 信号"""
        s = DualMAStrategy(fast=3, slow=5, quantity=0.01)
        # 前 5 根横盘,后 10 根急涨
        closes = [100] * 5 + [100 + i * 5 for i in range(1, 16)]
        for k in make_klines(closes):
            s.feed(k, closed=True)
        # 应至少有一个 BUY
        buys = [sig for sig in s.signals if sig.side == Side.BUY]
        assert len(buys) >= 1
        assert all(sig.symbol == "TESTUSDT" for sig in s.signals)

    def test_downtrend_generates_sell(self):
        """单边下跌 → 死叉 → SELL 信号"""
        s = DualMAStrategy(fast=3, slow=5, quantity=0.01)
        # 先涨后跌
        closes = [100 + i * 2 for i in range(10)] + [120 - i * 5 for i in range(1, 21)]
        for k in make_klines(closes):
            s.feed(k, closed=True)
        # 应至少有一个 SELL
        sells = [sig for sig in s.signals if sig.side == Side.SELL]
        assert len(sells) >= 1

    def test_insufficient_data_no_signal(self):
        s = DualMAStrategy(fast=5, slow=20, quantity=0.01)
        for k in make_klines([100] * 10):  # 只有 10 根,慢线需要 20
            s.feed(k, closed=True)
        assert len(s.signals) == 0
