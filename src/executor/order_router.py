"""
src/executor/order_router.py - L3 执行层

下单、撤单、改单,所有策略信号最终通过这里下单。
"""
import asyncio
from typing import Optional, List

from src.adapter.binance_cli import FuturesUSDS
from src.data.models import Side, OrderType
from src.logger import get_logger

log = get_logger("executor")


class OrderRouter:
    """订单路由"""

    def __init__(self, profile: Optional[str] = None, test_mode: bool = False):
        self.profile = profile
        self.test_mode = test_mode  # True: 走 test-order,真单

    def _warn_live(self):
        if not self.test_mode:
            log.warning("⚠️  实盘下单模式")

    # ==================== 下单 ====================

    async def market(
        self, symbol: str, side: Side, quantity: float,
        reduce_only: bool = False,
    ) -> dict:
        self._warn_live()
        log.info(f"[MARKET] {side.value} {symbol} qty={quantity} reduce={reduce_only}")
        return await FuturesUSDS.new_order(
            symbol=symbol, side=side.value, type_=OrderType.MARKET.value,
            quantity=quantity, reduce_only=reduce_only, test=self.test_mode,
        )

    async def limit(
        self, symbol: str, side: Side, quantity: float, price: float,
        time_in_force: str = "GTC", reduce_only: bool = False,
    ) -> dict:
        self._warn_live()
        log.info(f"[LIMIT ] {side.value} {symbol} qty={quantity} @ {price}")
        return await FuturesUSDS.new_order(
            symbol=symbol, side=side.value, type_=OrderType.LIMIT.value,
            quantity=quantity, price=price,
            time_in_force=time_in_force, reduce_only=reduce_only,
            test=self.test_mode,
        )

    async def stop_market(
        self, symbol: str, side: Side, quantity: float, stop_price: float,
        reduce_only: bool = True,
    ) -> dict:
        self._warn_live()
        log.info(f"[STOP  ] {side.value} {symbol} qty={quantity} stop={stop_price}")
        return await FuturesUSDS.new_order(
            symbol=symbol, side=side.value, type_="STOP_MARKET",
            quantity=quantity, stop_price=stop_price,
            reduce_only=reduce_only, test=self.test_mode,
        )

    # ==================== 撤单 ====================

    async def cancel(self, symbol: str, order_id: int) -> dict:
        log.info(f"撤单 {symbol} #{order_id}")
        return await FuturesUSDS.cancel_order(symbol, order_id=order_id)

    async def cancel_all(self, symbol: str) -> dict:
        log.info(f"全撤 {symbol} 所有挂单")
        return await FuturesUSDS.cancel_all(symbol)

    # ==================== 算法单(TP/SL)===================

    async def take_profit(
        self, symbol: str, side: Side, quantity: float, tp_price: float,
        reduce_only: bool = True,
    ) -> dict:
        """限价止盈"""
        return await FuturesUSDS.new_order(
            symbol=symbol, side=side.value, type="TAKE_PROFIT",
            quantity=quantity, price=tp_price, stop_price=tp_price,
            reduce_only=reduce_only, test=self.test_mode,
        )

    async def bracket(
        self, symbol: str, entry_side: Side, quantity: float,
        sl_price: float, tp_price: Optional[float] = None,
    ) -> List[dict]:
        """
        下止损单(可选同时下止盈单)
        返回 [止损单结果, 止盈单结果或 None]
        """
        # 止损方向:与开仓相反
        sl_side = Side.SELL if entry_side == Side.BUY else Side.BUY
        orders = []

        orders.append(await self.stop_market(
            symbol, sl_side, quantity, sl_price, reduce_only=True
        ))
        if tp_price:
            orders.append(await self.take_profit(
                symbol, sl_side, quantity, tp_price, reduce_only=True
            ))
        return orders


# ==================== 单独运行测试 ====================
if __name__ == "__main__":
    print("🔍 L3 执行层测试(默认 test_mode,不会真实下单)\n")

    async def test():
        router = OrderRouter(test_mode=True)
        try:
            print("测试限价买单(测试单)...")
            r = await router.limit(
                "BTCUSDT", Side.BUY, quantity=0.001, price=30000
            )
            print(f"   ✅ {r}\n")
        except Exception as e:
            print(f"   ❌ {e}\n")

    asyncio.run(test())
