"""
src/executor/position_sizer.py - 仓位大小计算

根据账户净值 + 配置参数,计算单币种下单数量。
"""
import sys
from pathlib import Path
from dataclasses import dataclass

# 让 `python src/executor/position_sizer.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import CONFIG


@dataclass
class PositionSize:
    symbol: str
    account_equity: float
    margin_pct: float              # 保证金占账户净值 %
    leverage: int
    entry_price: float             # 入场价
    margin_amount: float           # 保证金(USDT)
    notional: float                # 名义价值(USDT)
    quantity: float                # 下单数量(币种单位)
    side: str = "BUY"              # BUY / SELL

    def __str__(self):
        return (
            f"PositionSize({self.symbol} {self.side}: "
            f"equity=${self.account_equity:.2f} × {self.margin_pct}% "
            f"= ${self.margin_amount:.2f} 保证金 "
            f"× {self.leverage}x 杠杆 "
            f"= ${self.notional:.2f} 名义 "
            f"= {self.quantity} {self.symbol[:-4]})"
        )


def calc_position(
    symbol: str,
    account_equity: float,
    entry_price: float,
    side: str = "BUY",
    leverage: int = None,
    margin_pct: float = None,
) -> PositionSize:
    """
    计算下单数量

    公式:
        margin_amount = account_equity × margin_pct%
        notional = margin_amount × leverage
        quantity = notional / entry_price

    例: equity=100, margin_pct=4, leverage=20, BTC=$58,000
        margin = $4, notional = $80, quantity = 0.00137 BTC
    """
    cfg = CONFIG.trading
    leverage = leverage or cfg.leverage
    margin_pct = margin_pct or cfg.order_pct_of_margin

    margin_amount = account_equity * margin_pct / 100
    notional = margin_amount * leverage
    quantity = notional / entry_price if entry_price > 0 else 0

    return PositionSize(
        symbol=symbol,
        account_equity=account_equity,
        margin_pct=margin_pct,
        leverage=leverage,
        entry_price=entry_price,
        margin_amount=margin_amount,
        notional=notional,
        quantity=quantity,
        side=side,
    )


# 单独运行
if __name__ == "__main__":
    print("🧮 仓位大小计算器\n")

    # 场景 1: 账户 100 USDT, BTC $58,000
    ps = calc_position("BTCUSDT", 100, 58000)
    print(f"1. 账户 100 USDT, BTC $58,000")
    print(f"   {ps}\n")

    # 场景 2: 账户 1000 USDT, ETH $1,500
    ps = calc_position("ETHUSDT", 1000, 1500)
    print(f"2. 账户 1000 USDT, ETH $1,500")
    print(f"   {ps}\n")

    # 场景 3: 账户 10000 USDT, SOL $74
    ps = calc_position("SOLUSDT", 10000, 74)
    print(f"3. 账户 10000 USDT, SOL $74")
    print(f"   {ps}\n")

    # 场景 4: 空单
    ps = calc_position("BTCUSDT", 100, 58000, side="SELL")
    print(f"4. 空单(参数一样,仅 side 变化)")
    print(f"   {ps}")
