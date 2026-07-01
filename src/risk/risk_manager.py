"""
src/risk/risk_manager.py - L4 风控层

所有信号在下单前 / 持仓中都要过这里。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.data.models import Signal, Position, Balance, Side
from src.config import CONFIG
from src.logger import get_logger

log = get_logger("risk")


class RiskAction(Enum):
    """风控决策"""
    ALLOW = "ALLOW"           # 通过
    REJECT = "REJECT"         # 拒绝
    REDUCE = "REDUCE"         # 允许但缩仓


@dataclass
class RiskCheck:
    action: RiskAction
    reason: str = ""
    adjusted_quantity: Optional[float] = None

    @property
    def allowed(self) -> bool:
        return self.action in (RiskAction.ALLOW, RiskAction.REDUCE)


class RiskManager:
    """风控管理器"""

    def __init__(self, config=None):
        self.config = config or CONFIG.risk
        self.daily_pnl: float = 0.0
        self.peak_equity: float = 0.0
        self.frozen: bool = False
        self.freeze_reason: str = ""

    # ==================== 冷却 / 解冻 ====================

    def freeze(self, reason: str):
        """触发熔断"""
        self.frozen = True
        self.freeze_reason = reason
        log.error(f"🛑 风控熔断: {reason}")

    def unfreeze(self):
        self.frozen = False
        self.freeze_reason = ""
        log.warning("🟢 风控解除熔断")

    # ==================== 信号检查(下单前)===================

    def check_signal(
        self,
        signal: Signal,
        equity: float,
        current_position: Optional[Position] = None,
    ) -> RiskCheck:
        """对单个信号做风控检查"""

        # 1. 熔断
        if self.frozen:
            return RiskCheck(RiskAction.REJECT, f"系统熔断中: {self.freeze_reason}")

        # 2. 黑名单
        if signal.symbol in self.config.blacklist_symbols:
            return RiskCheck(RiskAction.REJECT, f"{signal.symbol} 在黑名单中")

        # 3. 日内亏损熔断
        if equity > 0:
            loss_pct = -self.daily_pnl / equity * 100
            if loss_pct >= self.config.max_daily_loss_pct:
                self.freeze(f"日内亏损 {loss_pct:.1f}% 超过限制 {self.config.max_daily_loss_pct}%")
                return RiskCheck(RiskAction.REJECT, "日内亏损超限")

        # 4. 仓位大小限制(仅对开仓信号)
        if not signal.reduce_only and equity > 0:
            notional = signal.quantity * (signal.price or 0)
            if notional > 0:
                pos_pct = notional / equity * 100
                if pos_pct > self.config.max_position_size_pct:
                    adjusted = signal.quantity * (self.config.max_position_size_pct / pos_pct)
                    log.warning(
                        f"仓位 {pos_pct:.1f}% 超过限制 {self.config.max_position_size_pct}%,"
                        f" 缩仓到 {adjusted:.4f}"
                    )
                    return RiskCheck(
                        RiskAction.REDUCE,
                        f"缩仓 {pos_pct:.1f}% → {self.config.max_position_size_pct}%",
                        adjusted_quantity=adjusted,
                    )

        return RiskCheck(RiskAction.ALLOW)

    # ==================== 持仓检查(运行时)===================

    def check_position(self, position: Position) -> RiskCheck:
        """检查持仓是否触发止损"""
        if position.entry_price <= 0:
            return RiskCheck(RiskAction.ALLOW)
        if position.side == Side.BUY:
            loss_pct = (position.entry_price - position.mark_price) / position.entry_price * 100
        else:
            loss_pct = (position.mark_price - position.entry_price) / position.entry_price * 100
        if loss_pct >= self.config.stop_loss_pct * 100 * position.leverage / 100:
            # 注:合约按杠杆放大
            return RiskCheck(
                RiskAction.REJECT,
                f"浮亏 {loss_pct:.2f}% 触发止损(未计杠杆)",
            )
        return RiskCheck(RiskAction.ALLOW)

    # ==================== 状态更新 ====================

    def on_fill(self, realized_pnl: float):
        """成交回报更新"""
        self.daily_pnl += realized_pnl

    def on_equity_update(self, equity: float):
        self.peak_equity = max(self.peak_equity, equity)

    def daily_drawdown_pct(self, current_equity: float) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - current_equity) / self.peak_equity * 100


# ==================== 单独运行测试 ====================
if __name__ == "__main__":
    print("🔍 L4 风控层测试\n")

    from src.data.models import Signal, Side

    rm = RiskManager()

    # 1. 正常信号
    sig = Signal(symbol="BTCUSDT", side=Side.BUY, quantity=0.001, price=60000, reason="test")
    check = rm.check_signal(sig, equity=10000)
    print(f"1️⃣  正常信号: {check.action.value} - {check.reason}")

    # 2. 黑名单
    sig.symbol = "DOGEUSDT"
    rm.config.blacklist_symbols = ["DOGEUSDT"]
    check = rm.check_signal(sig, equity=10000)
    print(f"2️⃣  黑名单: {check.action.value} - {check.reason}")

    # 3. 仓位超限
    sig.symbol = "BTCUSDT"
    sig.quantity = 1.0  # 1 BTC = 60000 USDT
    check = rm.check_signal(sig, equity=10000)  # 600%, 触发缩仓
    print(f"3️⃣  超大仓: {check.action.value} - {check.reason} → 缩到 {check.adjusted_quantity}")

    # 4. 日内熔断
    rm.daily_pnl = -1500  # 亏 1500 / 10000 = 15%
    check = rm.check_signal(sig, equity=10000)
    print(f"4️⃣  大亏日: {check.action.value} - {check.reason}")
    print(f"   frozen: {rm.frozen}, reason: {rm.freeze_reason}")

    print("\n🎉 L4 测试完成")
