"""
tests/test_risk.py - 风控测试
"""
import pytest
from src.risk.risk_manager import RiskManager, RiskAction
from src.data.models import Signal, Side


class TestRiskManager:
    def test_normal_signal_allowed(self):
        rm = RiskManager()
        sig = Signal("BTCUSDT", Side.BUY, 0.001, price=60000, reason="test")
        check = rm.check_signal(sig, equity=10000)
        assert check.allowed
        assert check.action == RiskAction.ALLOW

    def test_blacklist_rejects(self):
        rm = RiskManager()
        rm.config.blacklist_symbols = ["DOGEUSDT"]
        sig = Signal("DOGEUSDT", Side.BUY, 0.001, price=0.1, reason="test")
        check = rm.check_signal(sig, equity=10000)
        assert not check.allowed
        assert "黑名单" in check.reason

    def test_over_size_reduces(self):
        rm = RiskManager()
        # 100 BTC × 60000 = 6000000 USDT 名义 / 10000 equity = 600 倍 (= 60000%)
        # max_position_size_pct 默认 4%,所以应缩到 4% 仓位
        sig = Signal("BTCUSDT", Side.BUY, 100, price=60000, reason="test")
        check = rm.check_signal(sig, equity=10000)
        assert check.action == RiskAction.REDUCE
        assert check.adjusted_quantity is not None
        # 4% * 10000 = 400 USDT 名义 / 60000 = 0.00667 BTC
        expected = 0.04 * 10000 / 60000  # = 0.00667
        assert abs(check.adjusted_quantity - expected) < 1e-6

    def test_daily_loss_freeze(self):
        rm = RiskManager()
        rm.daily_pnl = -1500  # 亏 15% (假设 equity 10000)
        sig = Signal("BTCUSDT", Side.BUY, 0.001, price=60000, reason="test")
        check = rm.check_signal(sig, equity=10000)
        assert not check.allowed
        assert rm.frozen
        assert "日内亏损" in check.reason

    def test_freeze_unfreeze(self):
        rm = RiskManager()
        rm.freeze("test")
        assert rm.frozen
        rm.unfreeze()
        assert not rm.frozen

    def test_reduce_only_skips_size_check(self):
        rm = RiskManager()
        # 平仓不应受 30% 仓位限制
        sig = Signal("BTCUSDT", Side.SELL, 100, price=60000, reduce_only=True, reason="close")
        check = rm.check_signal(sig, equity=10000)
        assert check.action == RiskAction.ALLOW  # 不缩仓


class TestDrawdown:
    def test_peak_update(self):
        rm = RiskManager()
        rm.on_equity_update(10000)
        rm.on_equity_update(11000)
        rm.on_equity_update(9000)
        assert rm.peak_equity == 11000
        dd = rm.daily_drawdown_pct(9000)
        assert abs(dd - 18.18) < 0.1  # (11000-9000)/11000
