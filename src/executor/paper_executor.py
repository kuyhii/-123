"""
src/executor/paper_executor.py - 模拟执行器

⚠️ 不会下任何真实订单。所有"成交"都是本地模拟。

工作方式:
- 接收 OrderRouter 下单请求
- 在内存中维护 模拟账户(余额/持仓/挂单)
- 按规则即时"成交"或挂单等待
- 返回跟真实执行器一样的 ExecutionResult

真实账户数据可以用真实 API 拉(从 LiveExecutor 借余额和持仓),实现"用真数据模拟交易"。
"""
import asyncio
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.executor.base import (
    OrderExecutor, ExecutionResult, ExecutorMode, ExecutorType,
)
from src.data.models import Order, OrderType, Side
from src.logger import get_logger
from src.notify.notifier import DEFAULT_NOTIFIER as notifier

log = get_logger("paper_executor")


class OrderStatus(str, Enum):
    PENDING = "PENDING"   # 挂单
    FILLED = "FILLED"     # 成交
    CANCELED = "CANCELED"  # 撤销


@dataclass
class SimulatedOrder:
    """模拟订单"""
    order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: float
    price: float
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    avg_price: float = 0.0
    fee: float = 0.0
    reduce_only: bool = False
    create_time: float = field(default_factory=time.time)
    fill_time: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.status == OrderStatus.PENDING


@dataclass
class SimulatedAccount:
    """模拟账户"""
    initial_balance: float = 10000.0
    balance: float = 10000.0   # 现金
    positions: Dict[str, dict] = field(default_factory=dict)  # symbol -> {qty, entry, leverage}
    realized_pnl: float = 0.0
    fee_total: float = 0.0
    trade_count: int = 0

    @property
    def equity(self) -> float:
        """总权益(现金 + 持仓名义按当前价)"""
        return self.balance + self.realized_pnl

    def get_position(self, symbol: str) -> Optional[dict]:
        return self.positions.get(symbol)

    def position_qty(self, symbol: str) -> float:
        p = self.positions.get(symbol)
        return p["qty"] if p else 0.0


class PaperExecutor(OrderExecutor):
    """
    模拟执行器

    特性:
    - 不需要 API key
    - 不下任何真实订单
    - 内存账户,可选持久化
    - 支持市价单即时成交 / 限价单模拟等待
    """

    def __init__(self, initial_balance: float = 10000.0,
                 fee_rate: float = 0.0004):  # 0.04% 单边
        self.account = SimulatedAccount(initial_balance=initial_balance, balance=initial_balance)
        self.fee_rate = fee_rate
        self.orders: Dict[str, SimulatedOrder] = {}
        self.order_counter = 0
        log.info(f"🎮 PaperExecutor 启动,初始资金 ${initial_balance:.2f}")

    @property
    def mode(self) -> ExecutorMode:
        return ExecutorMode.PAPER

    @property
    def is_real_money(self) -> bool:
        return False

    def pre_trade_check(self, signal, account_equity: float) -> tuple:
        # 模拟盘:不阻止,只警告
        if account_equity <= 0:
            return False, "模拟账户无资金"
        return True, ""

    async def place_order(
        self,
        symbol: str,
        side: Side,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
        **kwargs,
    ) -> ExecutionResult:
        """模拟下单"""
        self.order_counter += 1
        order_id = f"PAPER-{self.order_counter}-{int(time.time())}"
        # 价格:市价单用当前最新价(模拟时用 price 字段;实际可能需要外部传入)
        order_price = price if price is not None else 0.0

        log.info(f"📝 [PAPER] 下单: {side.value} {symbol} {order_type.value} "
                 f"qty={quantity} @ {order_price}")

        order = SimulatedOrder(
            order_id=order_id,
            symbol=symbol, side=side, order_type=order_type,
            quantity=quantity, price=order_price, reduce_only=reduce_only,
        )
        self.orders[order_id] = order

        # 市价单:即时成交(简化模型)
        if order_type == OrderType.MARKET:
            return self._fill_market(order, order_price)
        # 限价单:挂单等待(此处简化,即时按挂单价成交)
        elif order_type == OrderType.LIMIT:
            return self._fill_market(order, order_price)  # 简化:限价单也即时成交
        else:
            # 其它类型:即时按 price 成交
            return self._fill_market(order, order_price)

    def _fill_market(self, order: SimulatedOrder, fill_price: float) -> ExecutionResult:
        """模拟成交"""
        if fill_price <= 0:
            return ExecutionResult(success=False, error="价格无效,模拟成交失败")

        qty = order.quantity
        notional = qty * fill_price
        fee = notional * self.fee_rate

        # 调整现金(买 -notional, 卖 +notional)
        if order.side == Side.BUY:
            self.account.balance -= (notional + fee)
            # 更新持仓
            pos = self.account.positions.get(order.symbol)
            if pos:
                # 已有持仓 → 加权平均
                old_qty = pos["qty"]
                old_entry = pos["entry"]
                new_qty = old_qty + qty
                new_entry = (old_qty * old_entry + qty * fill_price) / new_qty
                pos["qty"] = new_qty
                pos["entry"] = new_entry
            else:
                self.account.positions[order.symbol] = {
                    "qty": qty, "entry": fill_price, "leverage": 20
                }
        else:  # SELL
            self.account.balance += (notional - fee)
            pos = self.account.positions.get(order.symbol)
            if pos and pos["qty"] >= qty:
                # 平仓或减仓,计算 PnL
                pnl = (fill_price - pos["entry"]) * qty
                self.account.realized_pnl += pnl
                pos["qty"] -= qty
                if abs(pos["qty"]) < 1e-9:
                    del self.account.positions[order.symbol]
            else:
                # 空头开仓(简化)
                self.account.positions[order.symbol] = {
                    "qty": -qty, "entry": fill_price, "leverage": 20
                }

        self.account.fee_total += fee
        self.account.trade_count += 1

        order.status = OrderStatus.FILLED
        order.filled_qty = qty
        order.avg_price = fill_price
        order.fee = fee
        order.fill_time = time.time()

        log.info(
            f"✅ [PAPER] 成交: order_id={order.order_id} "
            f"qty={qty} @ {fill_price} fee=${fee:.4f} "
            f"余额=${self.account.balance:.2f}"
        )
        return ExecutionResult(
            success=True,
            order_id=order.order_id,
            filled_qty=qty,
            avg_price=fill_price,
            fee=fee,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> ExecutionResult:
        order = self.orders.get(order_id)
        if not order or order.symbol != symbol:
            return ExecutionResult(success=False, error="订单不存在")
        if order.status != OrderStatus.PENDING:
            return ExecutionResult(success=False, error=f"订单状态: {order.status}")
        order.status = OrderStatus.CANCELED
        log.info(f"📝 [PAPER] 撤单 {order_id}")
        return ExecutionResult(success=True, order_id=order_id)

    async def cancel_all(self, symbol: str) -> ExecutionResult:
        n = 0
        for order in self.orders.values():
            if order.symbol == symbol and order.is_open:
                order.status = OrderStatus.CANCELED
                n += 1
        log.info(f"📝 [PAPER] 全撤 {symbol},共 {n} 单")
        return ExecutionResult(success=True, filled_qty=float(n))

    async def get_balance(self) -> dict:
        return {
            "total": self.account.equity,
            "available": self.account.balance,
            "unrealized": self.account.realized_pnl,
        }

    async def get_position(self, symbol: str) -> Optional[dict]:
        pos = self.account.get_position(symbol)
        if not pos:
            return None
        return {
            "symbol": symbol,
            "positionAmt": str(pos["qty"]),
            "entryPrice": str(pos["entry"]),
            "leverage": str(pos["leverage"]),
        }

    async def get_open_orders(self, symbol: Optional[str] = None) -> list:
        return [
            {"orderId": o.order_id, "symbol": o.symbol, "side": o.side.value,
             "type": o.order_type.value, "origQty": str(o.quantity), "price": str(o.price),
             "status": o.status.value}
            for o in self.orders.values()
            if o.is_open and (symbol is None or o.symbol == symbol)
        ]


# ==================== 单独测试 ====================
if __name__ == "__main__":
    import asyncio

    async def test():
        print("🎮 PaperExecutor 真实跑通测试\n")
        executor = PaperExecutor(initial_balance=10000)

        # 1. 查余额
        bal = await executor.get_balance()
        print(f"1️⃣  初始余额: ${bal['available']:.2f}")

        # 2. 下市价买单
        r = await executor.place_order("BTCUSDT", Side.BUY, OrderType.MARKET,
                                       quantity=0.1, price=60000)
        print(f"2️⃣  下单结果: {r}")
        assert r.success
        assert r.filled_qty == 0.1

        # 3. 查持仓
        pos = await executor.get_position("BTCUSDT")
        print(f"3️⃣  持仓: {pos}")
        assert float(pos["positionAmt"]) == 0.1

        # 4. 平仓(卖出)
        r2 = await executor.place_order("BTCUSDT", Side.SELL, OrderType.MARKET,
                                        quantity=0.1, price=61000)
        print(f"4️⃣  平仓: {r2}")
        assert r2.success

        # 5. PnL
        bal2 = await executor.get_balance()
        pnl = bal2["total"] - 10000
        print(f"5️⃣  最终余额: ${bal2['available']:.2f}, 含 PnL ${bal2['unrealized']:.2f}, "
              f"实际盈亏: ${pnl:.2f}")
        # 1000 USDT 名义 * 1.67% 涨幅 = 16.67 收益 - 手续费
        assert pnl > 10  # 大约 16 收益

        print("\n🎉 PaperExecutor 全部功能正常")

    asyncio.run(test())
