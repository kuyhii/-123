"""
tests/test_executor.py - 执行器测试
"""
import pytest
import asyncio
import os
import sys
from pathlib import Path

# 用相对路径,适配任何机器
PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from src.executor.base import ExecutionResult, ExecutorMode
from src.executor.paper_executor import PaperExecutor, SimulatedOrder
from src.executor.order_router import OrderRouter
from src.data.models import Side, OrderType


class TestPaperExecutor:
    def setup_method(self):
        OrderRouter.reset()  # 清单例

    def test_initial_state(self):
        ex = PaperExecutor(initial_balance=10000)
        assert ex.is_real_money is False
        assert ex.mode == ExecutorMode.PAPER

    @pytest.mark.asyncio
    async def test_market_buy(self):
        ex = PaperExecutor(initial_balance=10000)
        r = await ex.place_order("BTCUSDT", Side.BUY, OrderType.MARKET,
                                 quantity=0.1, price=60000)
        assert r.success
        assert r.filled_qty == 0.1
        assert r.avg_price == 60000

        # 余额应减少
        bal = await ex.get_balance()
        # 初始 10000 - 6000 名义 - 手续费 ≈ 3997
        assert bal["available"] < 10000

        # 持仓应有
        pos = await ex.get_position("BTCUSDT")
        assert pos is not None
        assert float(pos["positionAmt"]) == 0.1

    @pytest.mark.asyncio
    async def test_market_sell_close_profit(self):
        ex = PaperExecutor(initial_balance=10000)
        # 买
        await ex.place_order("BTCUSDT", Side.BUY, OrderType.MARKET,
                             quantity=0.1, price=60000)
        # 涨价后卖
        r = await ex.place_order("BTCUSDT", Side.SELL, OrderType.MARKET,
                                 quantity=0.1, price=61000)
        assert r.success
        # PnL 应 ≈ 100(0.1 * 1000 涨幅) - 手续费
        bal = await ex.get_balance()
        # 收益 ≈ 100,扣手续费
        assert bal["available"] > 10000  # 有正收益
        # 持仓应平
        pos = await ex.get_position("BTCUSDT")
        assert pos is None

    @pytest.mark.asyncio
    async def test_limit_order(self):
        ex = PaperExecutor(initial_balance=10000)
        r = await ex.place_order("BTCUSDT", Side.BUY, OrderType.LIMIT,
                                 quantity=0.05, price=55000)
        assert r.success
        assert r.avg_price == 55000

    @pytest.mark.asyncio
    async def test_cancel_all(self):
        ex = PaperExecutor(initial_balance=10000)
        await ex.place_order("BTCUSDT", Side.BUY, OrderType.LIMIT,
                             quantity=0.01, price=50000)
        r = await ex.cancel_all("BTCUSDT")
        assert r.success

    def test_real_money_flag(self):
        ex = PaperExecutor()
        assert ex.is_real_money is False


class TestOrderRouter:
    def setup_method(self):
        OrderRouter.reset()

    def test_paper_router(self):
        r = OrderRouter(mode="paper", initial_balance=5000)
        assert r.is_real_money is False
        assert r.executor.mode == ExecutorMode.PAPER

    def test_singleton(self):
        r1 = OrderRouter(mode="paper")
        r2 = OrderRouter(mode="paper")
        assert r1 is r2

    def test_reset(self):
        r1 = OrderRouter(mode="paper", initial_balance=1000)
        OrderRouter.reset()
        r2 = OrderRouter(mode="paper", initial_balance=2000)
        assert r1 is not r2
        assert r2.executor.account.initial_balance == 2000

    @pytest.mark.asyncio
    async def test_paper_market_buy(self):
        OrderRouter.reset()
        r = OrderRouter(mode="paper", initial_balance=10000)
        result = await r.market("BTCUSDT", Side.BUY, 0.01)
        assert result.success
        assert result.filled_qty == 0.01

    @pytest.mark.asyncio
    async def test_paper_limit(self):
        OrderRouter.reset()
        r = OrderRouter(mode="paper", initial_balance=10000)
        result = await r.limit("ETHUSDT", Side.BUY, 0.5, 3000)
        assert result.success
        assert result.avg_price == 3000


class TestLiveExecutorSafety:
    """真实盘的安全测试(不需要真连币安)"""

    def setup_method(self):
        """每个测试前重置 CONFIG"""
        from src.config import CONFIG
        CONFIG.binance.env = "demo"
        CONFIG.binance.api_key = ""
        CONFIG.binance.secret_key = ""

    def test_requires_credentials(self, monkeypatch):
        # 直接改 CONFIG,绕开 dotenv 重载
        from src.executor.live_executor import LiveExecutor
        from src.config import CONFIG
        original_key = CONFIG.binance.api_key
        original_secret = CONFIG.binance.secret_key
        CONFIG.binance.api_key = ""
        CONFIG.binance.secret_key = ""
        try:
            with pytest.raises(RuntimeError, match="API_KEY"):
                LiveExecutor()
        finally:
            CONFIG.binance.api_key = original_key
            CONFIG.binance.secret_key = original_secret

    def test_invalid_env(self, monkeypatch):
        # 关键:LiveExecutor 已经 import 了 CONFIG,但 __init__ 每次都读
        # CONFIG.binance.env 是动态属性,所以改动立刻生效
        from src.executor.live_executor import LiveExecutor
        from src.config import CONFIG

        # 模拟 key 已配
        original_key = CONFIG.binance.api_key
        original_secret = CONFIG.binance.secret_key
        original_env = CONFIG.binance.env
        CONFIG.binance.api_key = "test_key"
        CONFIG.binance.secret_key = "test_secret"
        CONFIG.binance.env = "invalid"
        try:
            with pytest.raises(RuntimeError, match="BINANCE_API_ENV"):
                LiveExecutor()
        finally:
            CONFIG.binance.api_key = original_key
            CONFIG.binance.secret_key = original_secret
            CONFIG.binance.env = original_env

    def test_pre_trade_low_equity(self):
        # 直接 mock 配置
        from src.executor.live_executor import LiveExecutor
        # 不实际初始化(需要 API key),只测 pre_trade_check 的逻辑
        # 创建一个 mock 的 executor 行为
        class MockLive(LiveExecutor):
            def __init__(self): pass  # 跳过父类 __init__
        ex = MockLive()
        # pre_trade_check 是实例方法,需要 self.executor 接口
        # 用 Signal dataclass 测
        from src.data.models import Signal
        sig = Signal("BTCUSDT", Side.BUY, 0.001, price=60000, reason="test")
        ok, reason = ex.pre_trade_check(sig, account_equity=30)
        assert not ok
        assert "30" in reason  # 净值过低

    def test_pre_trade_huge_order(self):
        from src.executor.live_executor import LiveExecutor
        from src.data.models import Signal
        class MockLive(LiveExecutor):
            def __init__(self): pass
        ex = MockLive()
        # 单笔名义 > 50% 账户
        sig = Signal("BTCUSDT", Side.BUY, 1.0, price=60000)
        ok, reason = ex.pre_trade_check(sig, account_equity=10000)
        assert not ok
        assert "50%" in reason or "账户" in reason
