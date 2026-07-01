"""
src/executor/order_router.py - 订单路由(统一接口)

向后兼容旧版 API,内部根据 mode 自动选 LiveExecutor 或 PaperExecutor。
"""
import sys
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.executor.base import OrderExecutor, ExecutionResult
from src.executor.paper_executor import PaperExecutor
from src.executor.live_executor import LiveExecutor
from src.data.models import Side, OrderType
from src.config import CONFIG
from src.logger import get_logger

log = get_logger("order_router")


class OrderRouter:
    """
    订单路由器(单例)

    用法:
        router = OrderRouter(mode="paper")  # 或 "live"
        result = await router.market("BTCUSDT", Side.BUY, 0.001)
    """

    _instances: dict = {}

    def __new__(cls, mode: str = None, profile: str = None, **kwargs):
        mode = mode or CONFIG.executor_mode
        if mode in cls._instances:
            return cls._instances[mode]
        instance = super().__new__(cls)
        instance._initialized = False
        cls._instances[mode] = instance
        return instance

    def __init__(self, mode: str = None, profile: str = None, **kwargs):
        if self._initialized:
            return
        mode = mode or CONFIG.executor_mode
        self.mode = mode
        self.profile = profile or CONFIG.binance.profile
        self._kwargs = kwargs
        self._make_executor(mode)
        self._initialized = True

    def _make_executor(self, mode: str):
        if mode == "live":
            self.executor: OrderExecutor = LiveExecutor()
            log.warning("=" * 50)
            log.warning("⚠️  OrderRouter 使用 LIVE 执行器 - 真金白银")
            log.warning(f"   env={CONFIG.binance.env}, profile={self.profile}")
            log.warning("=" * 50)
        elif mode == "paper":
            initial = float(self._kwargs.get("initial_balance", 10000.0))
            self.executor: OrderExecutor = PaperExecutor(initial_balance=initial)
            log.info("🎮 OrderRouter 使用 PAPER 执行器 - 模拟交易")
        else:
            raise ValueError(f"未知 mode: {mode!r}, 必须是 'live' 或 'paper'")

    @classmethod
    def reset(cls):
        """重置单例(主要用于测试)"""
        cls._instances.clear()

    @property
    def is_real_money(self) -> bool:
        return self.executor.is_real_money

    def pre_trade_check(self, signal, account_equity: float) -> tuple:
        return self.executor.pre_trade_check(signal, account_equity)

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """获取当前市价(优先用真数据,失败则 None)"""
        try:
            from src.adapter.binance_cli import FuturesUSDS
            t = await FuturesUSDS.ticker_24h(symbol)
            return float(t.get("lastPrice", 0)) or None
        except Exception:
            return None

    async def market(
        self, symbol: str, side: Side, quantity: float,
        reduce_only: bool = False,
    ) -> ExecutionResult:
        # 自动获取市价(模拟盘没价格不能成交)
        price = await self._get_current_price(symbol)
        return await self.executor.place_order(
            symbol, side, OrderType.MARKET, quantity,
            price=price, reduce_only=reduce_only,
        )

    async def limit(
        self, symbol: str, side: Side, quantity: float, price: float,
        time_in_force: str = "GTC", reduce_only: bool = False,
    ) -> ExecutionResult:
        return await self.executor.place_order(
            symbol, side, OrderType.LIMIT, quantity,
            price=price, reduce_only=reduce_only, time_in_force=time_in_force,
        )

    async def stop_market(
        self, symbol: str, side: Side, quantity: float, stop_price: float,
        reduce_only: bool = True,
    ) -> ExecutionResult:
        return await self.executor.place_order(
            symbol, side, OrderType.STOP_MARKET, quantity,
            price=None, reduce_only=reduce_only, stop_price=stop_price,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> ExecutionResult:
        return await self.executor.cancel_order(symbol, order_id)

    async def cancel_all(self, symbol: str) -> ExecutionResult:
        return await self.executor.cancel_all(symbol)

    async def get_balance(self) -> dict:
        return await self.executor.get_balance()

    async def get_position(self, symbol: str):
        return await self.executor.get_position(symbol)

    async def get_open_orders(self, symbol: str = None):
        return await self.executor.get_open_orders(symbol)


# ==================== 单独测试 ====================
if __name__ == "__main__":
    import asyncio

    async def test():
        # 测试 paper 模式
        OrderRouter.reset()
        r = OrderRouter(mode="paper", initial_balance=10000)
        print(f"Router: {r.executor}")
        assert r.is_real_money is False

        bal = await r.get_balance()
        print(f"初始余额: ${bal['available']:.2f}")

        result = await r.market("BTCUSDT", Side.BUY, 0.01, )
        print(f"下单: {result}")
        assert result.success

        bal2 = await r.get_balance()
        print(f"下单后余额: ${bal2['available']:.2f}")

        print("\n🎉 OrderRouter(PAPER) 跑通")

    asyncio.run(test())
