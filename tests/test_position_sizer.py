"""
tests/test_position_sizer.py - 仓位计算测试
"""
import pytest
from src.executor.position_sizer import calc_position


class TestCalcPosition:
    def test_basic_4_pct_20x(self):
        """账户 100, 4% 保证金, 20x 杠杆"""
        ps = calc_position("BTCUSDT", 100, 58000)
        assert ps.margin_amount == 4.0
        assert ps.notional == 80.0
        assert abs(ps.quantity - (80 / 58000)) < 1e-9

    def test_different_equity(self):
        ps = calc_position("ETHUSDT", 1000, 1500)
        # 1000 * 4% = 40 保证金, 20x = 800 名义
        assert ps.margin_amount == 40.0
        assert ps.notional == 800.0
        assert abs(ps.quantity - (800 / 1500)) < 1e-9

    def test_zero_price_safe(self):
        ps = calc_position("BTCUSDT", 100, 0)
        assert ps.quantity == 0

    def test_short_side(self):
        ps = calc_position("BTCUSDT", 100, 58000, side="SELL")
        assert ps.side == "SELL"
        assert ps.margin_amount == 4.0  # 数量一样, 仅方向不同

    def test_overrides(self):
        ps = calc_position("BTCUSDT", 100, 58000, leverage=10, margin_pct=2.0)
        assert ps.leverage == 10
        assert ps.margin_pct == 2.0
        assert ps.margin_amount == 2.0
        assert ps.notional == 20.0
