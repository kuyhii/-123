"""
src/engine/paper_engine.py - 模拟盘引擎

实时拉行情 → 跑策略 → 模拟下单(不真下)→ 风控 → 报告 PnL
- 用 user-data WS 同步真实账户(可选,演示)
- 用 K线 WS 喂策略
- 用 TestOrderRouter 模拟下单回报
- 实时显示:价格、信号、模拟持仓、PnL

适合: 策略上线前最后验证、7×24 跑但不下单
"""
import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel

from src.config import CONFIG, PROJECT_ROOT
from src.logger import get_logger
from src.data.models import Kline, Signal
from src.strategy.base import Strategy
from src.strategy.factory import create as create_strategy
from src.executor.order_router import OrderRouter
from src.executor.position_sizer import calc_position
from src.risk.risk_manager import RiskManager
from src.data.ws_kline import KlineStream
from src.data.market_data import MarketData
from src.account.account import Account
from src.storage.db import (
    init_db, KlinesRepository, SignalsRepository, OrdersRepository, TradesRepository,
)
from src.notify.notifier import DEFAULT_NOTIFIER as notifier
from src.utils.health import HealthMonitor

log = get_logger("paper")
console = Console()


@dataclass
class SimulatedPosition:
    """模拟持仓(不依赖真实账户)"""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    entry_time: int
    leverage: int = 20

    def unrealized_pnl(self, mark_price: float) -> float:
        if self.side == "LONG":
            return (mark_price - self.entry_price) * self.quantity * self.leverage
        else:
            return (self.entry_price - mark_price) * abs(self.quantity) * self.leverage


@dataclass
class PaperState:
    """模拟盘运行时状态"""
    initial_equity: float = 1000.0
    equity: float = 1000.0
    cash: float = 1000.0
    positions: Dict[str, SimulatedPosition] = field(default_factory=dict)
    signals: List = field(default_factory=list)
    trades: List[dict] = field(default_factory=list)
    last_prices: Dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)

    def total_equity(self) -> float:
        u = sum(
            p.unrealized_pnl(self.last_prices.get(s, p.entry_price))
            for s, p in self.positions.items()
        )
        return self.cash + u


class PaperEngine:
    """
    模拟盘引擎

    用法:
        engine = PaperEngine(strategy="dual_ma", symbol="BTCUSDT", equity=1000)
        await engine.run(duration_minutes=60)  # 跑 60 分钟
    """

    def __init__(self, strategy: str, symbol: str,
                 equity: float = 1000.0, leverage: int = None):
        self.symbol = symbol
        self.strategy_name = strategy
        self.equity = equity
        self.leverage = leverage or CONFIG.trading.leverage

        self.risk = RiskManager()
        self.router = OrderRouter(test_mode=True)  # 永远 test_mode
        self.state = PaperState(initial_equity=equity, equity=equity, cash=equity)

        # 持久化
        init_db()
        self.klines_repo = KlinesRepository()
        self.signals_repo = SignalsRepository()
        self.orders_repo = OrdersRepository()
        self.trades_repo = TradesRepository()

    def _on_kline(self, kline: Kline):
        """K线回调:更新价格、喂策略、检测信号"""
        if kline.symbol != self.symbol:
            return
        self.state.last_prices[self.symbol] = kline.close

        # 喂策略
        sig = self.strategy.feed(kline, closed=getattr(kline, "is_closed", True))
        if sig and sig.symbol == self.symbol:
            self._handle_signal(sig, kline.close)

    def _handle_signal(self, sig, current_price: float):
        """处理策略信号:风控 → 仓位计算 → 模拟成交"""
        log.info(f"📡 信号: {sig.side.value} {sig.symbol} qty={sig.quantity} ({sig.reason})")
        notifier.signal(sig.symbol, sig.side.value, sig.reason)

        # 风控检查
        check = self.risk.check_signal(sig, equity=self.state.total_equity())
        if not check.allowed:
            log.warning(f"❌ 风控拒绝: {check.reason}")
            return

        # 调整仓位
        qty = check.adjusted_quantity if check.adjusted_quantity else sig.quantity

        # 模拟成交
        side = "LONG" if sig.side.value == "BUY" else "SHORT"

        # 简单模型:如有反向持仓,先平仓
        existing = self.state.positions.get(self.symbol)
        if existing and existing.side != side:
            self._close_position(existing, current_price)

        # 开仓
        pos = SimulatedPosition(
            symbol=self.symbol, side=side, quantity=qty,
            entry_price=current_price, entry_time=int(time.time() * 1000),
            leverage=self.leverage,
        )
        self.state.positions[self.symbol] = pos

        # 扣保证金
        notional = qty * current_price
        margin = notional / self.leverage
        self.state.cash -= margin

        # 记录
        self.signals_repo.log(sig)
        self.trades_repo.log(
            symbol=self.symbol, side=side,
            quantity=qty, price=current_price, realized_pnl=0,
            fee=margin * 0.001, note=sig.reason,
        )

        log.info(
            f"✅ 开仓 {side} {qty} @ {current_price} "
            f"(保证金 ${margin:.2f}, 剩余现金 ${self.state.cash:.2f})"
        )

    def _close_position(self, pos: SimulatedPosition, current_price: float):
        """平仓并结算 PnL"""
        pnl = pos.unrealized_pnl(current_price)
        # 退保证金 + PnL
        notional = pos.quantity * pos.entry_price
        margin_back = notional / pos.leverage
        self.state.cash += margin_back + pnl
        # 已实现 PnL
        self.risk.on_fill(pnl)
        # 记录
        self.trades_repo.log(
            symbol=pos.symbol, side="CLOSE",
            quantity=pos.quantity, price=current_price,
            realized_pnl=pnl, fee=margin_back * 0.001,
            note=f"close {pos.side}",
        )
        log.info(
            f"📤 平仓 {pos.side} {pos.quantity} @ {current_price} "
            f"PnL = ${pnl:+.2f}"
        )
        del self.state.positions[pos.symbol]

    def _make_dashboard(self) -> Table:
        """生成实时面板"""
        t = Table(title="📊 Paper Trading Dashboard", show_header=True)
        t.add_column("Symbol", style="cyan")
        t.add_column("Side", style="magenta")
        t.add_column("Qty", justify="right")
        t.add_column("Entry", justify="right")
        t.add_column("Mark", justify="right")
        t.add_column("PnL", justify="right", style="bold")
        t.add_column("Equity", justify="right", style="green")

        for sym, pos in self.state.positions.items():
            mark = self.state.last_prices.get(sym, pos.entry_price)
            pnl = pos.unrealized_pnl(mark)
            eq = self.state.total_equity()
            t.add_row(
                sym, pos.side, f"{pos.quantity:.4f}",
                f"{pos.entry_price:.2f}", f"{mark:.2f}",
                f"{pnl:+.2f}", f"{eq:.2f}"
            )
        if not self.state.positions:
            eq = self.state.total_equity()
            t.add_row("—", "—", "—", "—", "—", "—", f"{eq:.2f}")
        return t

    async def run(self, duration_minutes: int = 60):
        """主循环:订阅 K线 + 显示面板"""
        self.strategy = create_strategy(self.strategy_name, quantity=0.001)
        # 注册健康检查
        health = HealthMonitor.get()
        health.register("paper_engine")
        health.register("kline_ws")

        log.info(f"🚀 启动模拟盘: {self.strategy_name} on {self.symbol}")
        notifier.info("模拟盘启动", f"{self.strategy_name} on {self.symbol}, 资金 ${self.equity}")

        stream = KlineStream(self.symbol, "1m")
        end_time = time.time() + duration_minutes * 60

        with Live(self._make_dashboard(), refresh_per_second=2, console=console) as live:
            try:
                async for kline in stream.subscribe(on_kline=self._on_kline):
                    health.record_success("kline_ws")
                    health.record_success("paper_engine")
                    if time.time() > end_time:
                        log.info("⏱️  到时,结束")
                        break
                    live.update(self._make_dashboard())
            except KeyboardInterrupt:
                log.info("⏹️  用户中断")
                notifier.warn("模拟盘中断", "用户 Ctrl+C")
            except FileNotFoundError as e:
                log.error(f"❌ {e}")
                health.record_error("kline_ws", str(e))
                notifier.error("binance-cli 缺失", str(e))
                return
            except Exception as e:
                log.error(f"❌ 异常: {e}")
                health.record_error("paper_engine", str(e))
                notifier.error("模拟盘异常", str(e))

        # 收尾:平掉所有持仓
        if self.symbol in self.state.positions:
            last = self.state.last_prices.get(self.symbol, 0)
            self._close_position(self.state.positions[self.symbol], last)

        # 报告
        final_equity = self.state.total_equity()
        pnl = final_equity - self.initial_equity
        console.print(Panel(
            f"[bold green]初始: ${self.initial_equity:.2f}[/bold green]\n"
            f"[bold {'green' if pnl >= 0 else 'red'}]最终: ${final_equity:.2f}[/bold]\n"
            f"[bold]PnL:   ${pnl:+.2f} ({pnl/self.initial_equity*100:+.2f}%)[/bold]\n"
            f"交易次数: {len(self.trades_repo.recent(1000))}",
            title="📊 模拟盘结果"
        ))


# ==================== 单独运行 ====================
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="模拟盘引擎")
    p.add_argument("--strategy", default="dual_ma", help="策略名")
    p.add_argument("--symbol", default="BTCUSDT", help="交易对")
    p.add_argument("--equity", type=float, default=1000.0, help="初始资金")
    p.add_argument("--duration", type=int, default=60, help="持续分钟")
    args = p.parse_args()

    engine = PaperEngine(
        strategy=args.strategy, symbol=args.symbol,
        equity=args.equity,
    )
    try:
        asyncio.run(engine.run(duration_minutes=args.duration))
    except KeyboardInterrupt:
        print("\n⏹️  退出")
