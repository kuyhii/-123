"""
tests/test_data_models.py - 数据类测试
"""
import pytest
from src.data.models import (
    Kline, OrderBook, Ticker24h, MarkPrice,
    Position, Order, Signal, Side, OrderType, PositionSide, MarginType,
)


class TestKline:
    def test_from_binance(self):
        # Binance K线格式: [openTime, open, high, low, close, volume, closeTime, ...]
        k = Kline.from_binance(
            [1700000000000, "100", "105", "99", "103", "1000",
             1700003600000, "103000", 100, "0", "0", "0"],
            "BTCUSDT"
        )
        assert k.symbol == "BTCUSDT"
        assert k.open == 100.0
        assert k.high == 105.0
        assert k.close == 103.0
        assert k.volume == 1000.0
        assert k.quote_volume == 103000.0
        assert k.trades == 100

    def test_minimal_array(self):
        # 只有 7 个字段(老格式)
        k = Kline.from_binance(
            [1700000000000, "100", "105", "99", "103", "1000", 1700003600000],
            "BTCUSDT"
        )
        assert k.close == 103.0
        assert k.quote_volume == 0.0  # 默认值


class TestPosition:
    def test_long_position(self):
        p = Position.from_binance({
            "symbol": "BTCUSDT",
            "positionAmt": "0.5",
            "entryPrice": "60000",
            "markPrice": "61000",
            "unRealizedProfit": "500",
            "leverage": "10",
            "marginType": "ISOLATED",
            "liquidationPrice": "55000",
        })
        assert p is not None
        assert p.side == PositionSide.LONG
        assert p.quantity == 0.5
        assert p.notional == 30500.0  # 0.5 * 61000
        assert p.margin == 3050.0    # 30500 / 10

    def test_short_position(self):
        p = Position.from_binance({
            "symbol": "BTCUSDT",
            "positionAmt": "-0.3",
            "entryPrice": "60000",
            "markPrice": "59000",
            "unRealizedProfit": "300",
            "leverage": "10",
            "marginType": "CROSSED",
        })
        assert p.side == PositionSide.SHORT
        assert p.quantity == -0.3
        assert p.margin_type == MarginType.CROSSED

    def test_empty_position(self):
        p = Position.from_binance({"symbol": "BTCUSDT", "positionAmt": "0"})
        assert p is None


class TestSignal:
    def test_str(self):
        sig = Signal("BTCUSDT", Side.BUY, 0.001, price=60000, reason="test")
        s = str(sig)
        assert "BTCUSDT" in s
        assert "BUY" in s
        assert "test" in s
        # 可选字段不出现
        assert "SL=" not in s
        assert "TP=" not in s

    def test_with_sl_tp(self):
        sig = Signal(
            "BTCUSDT", Side.SELL, 0.001, price=60000,
            stop_loss=58000, take_profit=62000, reason="test"
        )
        s = str(sig)
        assert "SL=58000" in s
        assert "TP=62000" in s
