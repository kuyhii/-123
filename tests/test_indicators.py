"""
tests/test_indicators.py - 手写技术指标测试
"""
import pytest
from src.data.market_data import sma, ema, rsi


class TestSMA:
    def test_basic(self):
        assert sma([1, 2, 3, 4, 5], 3) == 4.0  # (3+4+5)/3
        assert sma([10, 20, 30], 2) == 25.0
        assert sma([5, 5, 5, 5], 4) == 5.0

    def test_insufficient_data(self):
        assert sma([1, 2], 5) is None

    def test_exact_period(self):
        assert sma([1, 2, 3], 3) == 2.0


class TestEMA:
    def test_basic(self):
        v = ema([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5)
        # EMA 起始用前 5 个 SMA = 3,后续 9 个加权
        assert v is not None
        assert 3 < v < 10  # 合理范围

    def test_insufficient_data(self):
        assert ema([1, 2, 3], 5) is None


class TestRSI:
    def test_overbought(self):
        # 连续上涨 → RSI 接近 100
        closes = [100 + i for i in range(20)]
        r = rsi(closes, 14)
        assert r is not None
        assert r > 80

    def test_oversold(self):
        closes = [100 - i for i in range(20)]
        r = rsi(closes, 14)
        assert r is not None
        assert r < 20

    def test_insufficient_data(self):
        assert rsi([1, 2, 3], 14) is None

    def test_neutral(self):
        # 横盘 → RSI 接近 50
        closes = [100 + (1 if i % 2 == 0 else -1) for i in range(20)]
        r = rsi(closes, 14)
        assert r is not None
        assert 40 < r < 60
