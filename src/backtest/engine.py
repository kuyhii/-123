"""
src/backtest/engine.py - 回测引擎

拉历史 K 线,跑策略,统计性能。
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Type
from datetime import datetime

from src.adapter.binance_cli import FuturesUSDS
from src.data.models import Kline, Side
from src.data.market_data import MarketData
from src.strategy.base import Strategy
from src.logger import get_logger

log = get_logger("backtest")


@dataclass
class BacktestResult:
    initial_equity: float
    final_equity: float
    total_pnl: float
    total_return: float
    trades: int
    wins: int
    losses: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float

    def summary(self) -> str:
        return (
            f"\n📊 回测结果\n"
            f"   初始资金:  {self.initial_equity:>10.2f}\n"
            f"   最终资金:  {self.final_equity:>10.2f}\n"
            f"   总盈亏:    {self.total_pnl:>10.2f}\n"
            f"   收益率:    {self.total_return*100:>9.2f}%\n"
            f"   交易次数:  {self.trades:>10d}\n"
            f"   胜率:      {self.win_rate*100:>9.2f}%\n"
            f"   最大回撤:  {self.max_drawdown*100:>9.2f}%\n"
            f"   夏普比率:  {self.sharpe_ratio:>10.2f}\n"
        )


class BacktestEngine:
    """简单回测引擎(单标的、现货模式近似)"""

    def __init__(
        self,
        strategy: Strategy,
        symbol: str,
        interval: str = "1h",
        days: int = 90,
        initial_equity: float = 10000.0,
        leverage: int = 1,
        fee_rate: float = 0.0004,  # 0.04% 单边
    ):
        self.strategy = strategy
        self.symbol = symbol
        self.interval = interval
        self.days = days
        self.equity = initial_equity
        self.initial_equity = initial_equity
        self.leverage = leverage
        self.fee_rate = fee_rate

        # 回测状态
        self.position = 0.0          # +正数=多, -负数=空
        self.entry_price = 0.0
        self.equity_curve: List[float] = [initial_equity]
        self.trade_log: List[dict] = []
        self.peak_equity = initial_equity

    async def _fetch_history(self) -> List[Kline]:
        """拉历史 K 线(分页拼到 days 长度)"""
        # K线根数估算:24h * days(1h 周期为例)
        total = 24 * self.days
        # 单次最多 1500, 多次拉
        all_klines: List[Kline] = []
        end_time = None
        pages = (total // 1500) + 1

        for _ in range(pages):
            kwargs = {"limit": 1500}
            if end_time:
                kwargs["end_time"] = end_time
            raw = await FuturesUSDS.kline(self.symbol, self.interval, **kwargs)
            if not raw:
                break
            page = [Kline.from_binance(k, self.symbol) for k in raw]
            all_klines = page + all_klines  # 倒序拼回去
            end_time = page[0].open_time - 1
            if len(page) < 1500:
                break
            await asyncio.sleep(0.1)  # 限流保护

        return all_klines

    def _execute(self, kline: Kline, signal) -> None:
        """执行信号(简化:即时成交,扣手续费)"""
        if signal.side == Side.BUY:
            qty_change = signal.quantity
        else:
            qty_change = -signal.quantity

        # 平仓反开
        if self.position != 0 and (self.position > 0) != (qty_change > 0):
            # 平仓
            close_qty = min(abs(self.position), abs(qty_change))
            pnl = close_qty * (kline.close - self.entry_price) * (1 if self.position > 0 else -1)
            pnl *= self.leverage
            self.equity += pnl - close_qty * kline.close * self.fee_rate * 2 * self.leverage
            self.trade_log.append({
                "time": kline.open_time, "side": "CLOSE",
                "price": kline.close, "qty": close_qty, "pnl": pnl,
            })
            self.position = 0
            self.entry_price = 0

        # 开仓
        if abs(qty_change) > abs(self.position):
            open_qty = abs(qty_change) - abs(self.position)
            self.position = qty_change
            self.entry_price = kline.close
            fee = open_qty * kline.close * self.fee_rate * 2 * self.leverage
            self.equity -= fee
            self.trade_log.append({
                "time": kline.open_time, "side": "OPEN",
                "price": kline.close, "qty": open_qty, "pnl": -fee,
            })

    async def run(self) -> BacktestResult:
        log.info(f"开始回测: {self.symbol} {self.interval} {self.days} 天")
        klines = await self._fetch_history()
        log.info(f"拿到 {len(klines)} 根 K 线")

        await self.strategy.on_init()
        for k in klines:
            sig = self.strategy.feed(k, closed=True)
            if sig:
                self._execute(k, sig)

            # 计算浮动权益
            if self.position != 0:
                unrealized = self.position * (k.close - self.entry_price) * self.leverage
                cur_equity = self.equity + unrealized
            else:
                cur_equity = self.equity
            self.equity_curve.append(cur_equity)
            self.peak_equity = max(self.peak_equity, cur_equity)

        await self.strategy.on_stop()
        return self._compute_result()

    def _compute_result(self) -> BacktestResult:
        # 最后一根 K 线强制平仓
        if self.position != 0 and self.equity_curve:
            last_eq = self.equity_curve[-1]
        else:
            last_eq = self.equity_curve[-1] if self.equity_curve else self.initial_equity

        # 简化统计
        closes = [t["pnl"] for t in self.trade_log if t["side"] == "CLOSE"]
        wins = sum(1 for p in closes if p > 0)
        losses = sum(1 for p in closes if p < 0)

        # 最大回撤
        max_dd = 0.0
        peak = self.initial_equity
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            max_dd = max(max_dd, dd)

        # 简化夏普(每日收益)
        if len(self.equity_curve) > 1:
            daily_returns = []
            for i in range(1, len(self.equity_curve)):
                prev = self.equity_curve[i - 1]
                if prev > 0:
                    daily_returns.append((self.equity_curve[i] - prev) / prev)
            if daily_returns:
                avg = sum(daily_returns) / len(daily_returns)
                var = sum((r - avg) ** 2 for r in daily_returns) / len(daily_returns)
                std = var ** 0.5
                sharpe = (avg / std) * (252 ** 0.5) if std > 0 else 0
            else:
                sharpe = 0
        else:
            sharpe = 0

        total_pnl = last_eq - self.initial_equity
        return BacktestResult(
            initial_equity=self.initial_equity,
            final_equity=last_eq,
            total_pnl=total_pnl,
            total_return=total_pnl / self.initial_equity if self.initial_equity > 0 else 0,
            trades=len(closes),
            wins=wins,
            losses=losses,
            win_rate=wins / len(closes) if closes else 0,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
        )


# 单独运行测试
if __name__ == "__main__":
    print("🔍 回测引擎测试\n")
    from src.strategy.examples.dual_ma import DualMAStrategy

    async def test():
        engine = BacktestEngine(
            strategy=DualMAStrategy(fast=5, slow=20, quantity=0.01),
            symbol="BTCUSDT",
            interval="1h",
            days=7,
            initial_equity=10000,
            leverage=10,
        )
        result = await engine.run()
        print(result.summary())

    try:
        asyncio.run(test())
    except Exception as e:
        print(f"❌ {e}")
