"""
src/account/account.py - L2 账户层

查询账户状态:余额、持仓、订单。
支持实时缓存。
"""
import asyncio
from typing import List, Optional, Dict

from src.adapter.binance_cli import FuturesUSDS
from src.data.models import Balance, Position, Order, PositionSide
from src.logger import get_logger

log = get_logger("account")


class Account:
    """账户状态"""

    def __init__(self, profile: Optional[str] = None):
        self.profile = profile
        self._balances: Dict[str, Balance] = {}
        self._positions: Dict[str, Position] = {}

    # ==================== 查询 ====================

    async def refresh(self) -> None:
        """刷新余额和持仓缓存"""
        await asyncio.gather(
            self.refresh_balances(),
            self.refresh_positions(),
        )

    async def refresh_balances(self) -> Dict[str, Balance]:
        """刷新余额"""
        raw = await FuturesUSDS.account_balance()
        self._balances = {
            b["asset"]: Balance.from_binance(b)
            for b in raw
            if float(b.get("balance", 0)) > 0 or float(b.get("availableBalance", 0)) > 0
        }
        return self._balances

    async def refresh_positions(self) -> Dict[str, Position]:
        """刷新持仓"""
        raw = await FuturesUSDS.position()
        self._positions = {}
        for p in raw:
            pos = Position.from_binance(p)
            if pos:
                self._positions[pos.symbol] = pos
        return self._positions

    # ==================== 便捷访问 ====================

    @property
    def balances(self) -> Dict[str, Balance]:
        return dict(self._balances)

    @property
    def positions(self) -> Dict[str, Position]:
        return dict(self._positions)

    def usdt_balance(self) -> Balance:
        """USDT 余额(合约账户保证金币)"""
        return self._balances.get("USDT", Balance(
            asset="USDT", balance=0, available_balance=0
        ))

    def total_equity(self) -> float:
        """总权益(余额 + 未实现盈亏)"""
        usdt = self.usdt_balance()
        unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        return usdt.balance + unrealized

    def available_balance(self) -> float:
        """可用余额"""
        return self.usdt_balance().available_balance

    def get_position(self, symbol: str) -> Optional[Position]:
        return self._positions.get(symbol)

    def position_notional(self, symbol: str) -> float:
        """某交易对的持仓名义价值"""
        p = self.get_position(symbol)
        return p.notional if p else 0.0

    # ==================== 账户设置 ====================

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        log.info(f"设置杠杆 {symbol} = {leverage}x")
        return await FuturesUSDS.set_leverage(symbol, leverage)

    async def set_margin_type(self, symbol: str, margin_type: str) -> dict:
        log.info(f"设置保证金模式 {symbol} = {margin_type}")
        return await FuturesUSDS.set_margin_type(symbol, margin_type)

    # ==================== 单独运行测试 ====================
    if __name__ == "__main__":
        pass


# 单独运行
if __name__ == "__main__":
    print("🔍 L2 账户层测试\n")

    async def test():
        acc = Account()
        try:
            print("刷新余额...")
            balances = await acc.refresh_balances()
            usdt = acc.usdt_balance()
            print(f"   ✅ USDT 余额: {usdt.balance:.2f}, 可用: {usdt.available_balance:.2f}")

            print("\n刷新持仓...")
            positions = await acc.refresh_positions()
            print(f"   ✅ 持仓数: {len(positions)}")
            for sym, p in positions.items():
                print(f"      {sym}: {p.side.value} qty={p.quantity} entry={p.entry_price} PnL={p.unrealized_pnl:.2f}")

            print(f"\n💰 总权益: {acc.total_equity():.2f} USDT")
        except Exception as e:
            print(f"❌ {e}")

    asyncio.run(test())
