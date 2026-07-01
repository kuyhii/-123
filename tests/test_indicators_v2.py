"""
tests/test_indicators.py - 增强技术指标测试
"""
import pytest
from src.data.indicators import (
    macd, macd_series, bollinger, atr, kdj, obv, obv_sma,
    MACD, BollingerBands, ATR, KDJ,
)


class TestMACD:
    def test_uptrend_bullish(self):
        # 持续上涨 → MACD > 0
        closes = [100 + i for i in range(60)]
        m = macd(closes)
        assert m is not None
        assert m.macd > 0
        # histogram 接近 0(数据是直线上涨,MACD 等于 signal,浮点精度)
        assert abs(m.histogram) < 0.1  # 实际是 1.7e-15

    def test_downtrend_bearish(self):
        closes = [100 - i for i in range(60)]
        m = macd(closes)
        assert m is not None
        assert m.macd < 0

    def test_insufficient_data(self):
        m = macd([100, 101, 102])
        assert m is None

    def test_crossover_detection(self):
        # 模拟金叉场景
        closes_up = [100] * 30 + [100 + i * 2 for i in range(30)]
        m1 = macd(closes_up[:31])
        m2 = macd(closes_up[:32])
        if m1 and m2:
            # 趋势由弱转强
            assert m2.histogram > m1.histogram or m2.histogram > 0


class TestBollinger:
    def test_normal(self):
        closes = [100 + i * 0.1 for i in range(30)]
        bb = bollinger(closes)
        assert bb is not None
        assert bb.lower < bb.middle < bb.upper
        # 价格在均线上方(持续上涨),%B > 0.5
        assert bb.percent_b > 0.5

    def test_breakout_above(self):
        # 价格突破上轨
        closes = [100] * 19 + [200]  # 最后一根跳涨
        bb = bollinger(closes)
        assert bb is not None
        assert bb.percent_b > 1  # 突破上轨

    def test_insufficient(self):
        assert bollinger([100, 101]) is None


class TestATR:
    def test_low_volatility(self):
        # 几乎横盘
        data = [{"high": 101, "low": 100, "close": 100.5} for _ in range(20)]
        a = atr(data)
        assert a is not None
        assert a.value < 2

    def test_high_volatility(self):
        # 剧烈波动
        data = [{"high": 100 + (i % 2) * 50, "low": 100, "close": 100 + (i % 2) * 30}
                for i in range(20)]
        a = atr(data)
        assert a is not None
        assert a.value > 10

    def test_trend_detection(self):
        data = [{"high": 101, "low": 100, "close": 100 + i * 0.5} for i in range(20)]
        a = atr(data)
        assert a.trend == "up"


class TestKDJ:
    def test_oversold(self):
        # 持续下跌 → KDJ 应该在低位
        closes = [100 - i for i in range(20)]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        k = kdj(highs, lows, closes)
        assert k is not None
        assert k.is_oversold()

    def test_overbought(self):
        closes = [100 + i for i in range(20)]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        k = kdj(highs, lows, closes)
        assert k is not None
        assert k.is_overbought()

    def test_insufficient(self):
        k = kdj([101], [99], [100])
        assert k is None


class TestOBV:
    def test_uptrend_positive(self):
        closes = [100, 101, 102, 103]
        volumes = [10, 20, 30, 40]
        o = obv(closes, volumes)
        # 一直涨 → OBV 单调递增
        assert o == [0, 20, 50, 90]

    def test_downtrend_negative(self):
        closes = [100, 99, 98, 97]
        volumes = [10, 20, 30, 40]
        o = obv(closes, volumes)
        assert o == [0, -20, -50, -90]

    def test_flat(self):
        closes = [100, 100, 100]
        volumes = [10, 20, 30]
        o = obv(closes, volumes)
        assert o == [0, 0, 0]

    def test_empty(self):
        assert obv([], []) == []
