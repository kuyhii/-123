"""
src/backtest/multi_engine.py - 多币种批量回测

从 config/trading_pairs.json 读取 40 个币种,逐个跑回测,
然后做组合汇总(等权加权)。

设计:
- 单币种回测复用 engine.BacktestEngine
- 并行执行(asyncio.gather)
- 输出每个币种的指标 + 组合指标
"""
import sys
import asyncio
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.backtest.engine import BacktestEngine, BacktestResult
from src.strategy.trading_pairs import load_pairs
from src.strategy.factory import create as create_strategy
from src.config import CONFIG
from src.logger import get_logger

log = get_logger("multi_backtest")


@dataclass
class MultiBacktestReport:
    """多币种回测汇总"""
    strategy: str
    interval: str
    days: int
    initial_equity_per_symbol: float
    leverage: int
    per_symbol: Dict[str, BacktestResult] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    duration_sec: float = 0.0

    @property
    def total_final_equity(self) -> float:
        return sum(r.final_equity for r in self.per_symbol.values())

    @property
    def total_pnl(self) -> float:
        return self.total_final_equity - (
            self.initial_equity_per_symbol * len(self.per_symbol)
        )

    @property
    def total_return(self) -> float:
        initial = self.initial_equity_per_symbol * len(self.per_symbol)
        return self.total_pnl / initial if initial > 0 else 0

    @property
    def total_trades(self) -> int:
        return sum(r.trades for r in self.per_symbol.values())

    @property
    def avg_win_rate(self) -> float:
        rates = [r.win_rate for r in self.per_symbol.values() if r.trades > 0]
        return sum(rates) / len(rates) if rates else 0

    @property
    def avg_sharpe(self) -> float:
        vals = [r.sharpe_ratio for r in self.per_symbol.values()]
        return sum(vals) / len(vals) if vals else 0

    @property
    def max_drawdown(self) -> float:
        return max((r.max_drawdown for r in self.per_symbol.values()),
                   default=0)

    def summary(self) -> str:
        lines = [
            "",
            "=" * 70,
            f"📊 多币种回测汇总 - {self.strategy} on {len(self.per_symbol)} 个币种",
            "=" * 70,
            f"周期: {self.interval} | 天数: {self.days} | 杠杆: {self.leverage}x",
            f"每币种初始: ${self.initial_equity_per_symbol:.2f}",
            f"组合初始:   ${self.initial_equity_per_symbol * len(self.per_symbol):.2f}",
            "",
            f"组合最终:   ${self.total_final_equity:.2f}",
            f"组合总盈亏: ${self.total_pnl:+.2f} ({self.total_return*100:+.2f}%)",
            f"总交易次数: {self.total_trades}",
            f"平均胜率:   {self.avg_win_rate*100:.2f}%",
            f"平均夏普:   {self.avg_sharpe:.2f}",
            f"最大回撤:   {self.max_drawdown*100:.2f}% (单币种最大)",
            f"耗时:       {self.duration_sec:.1f}s",
            "",
            f"📈 各币种明细 (按收益率排序):",
            "-" * 70,
            f"{'币种':<14}{'盈亏':>10}{'收益率':>10}{'胜率':>8}{'夏普':>8}{'回撤':>8}{'交易':>6}",
        ]
        # 按收益率排序
        sorted_results = sorted(
            self.per_symbol.items(),
            key=lambda kv: kv[1].total_return,
            reverse=True
        )
        for sym, r in sorted_results:
            lines.append(
                f"{sym:<14}"
                f"{r.total_pnl:>9.2f} "
                f"{r.total_return*100:>9.2f}% "
                f"{r.win_rate*100:>7.1f}% "
                f"{r.sharpe_ratio:>8.2f} "
                f"{r.max_drawdown*100:>7.2f}% "
                f"{r.trades:>5d}"
            )
        if self.errors:
            lines.append("")
            lines.append(f"❌ 失败币种 ({len(self.errors)}):")
            for sym, err in list(self.errors.items())[:5]:
                lines.append(f"   {sym}: {err[:60]}")
        return "\n".join(lines)


async def _run_one(symbol: str, strategy_name: str, interval: str,
                  days: int, equity: float, leverage: int) -> BacktestResult:
    """跑一个币种"""
    strategy = create_strategy(strategy_name, quantity=0.001)
    engine = BacktestEngine(
        strategy=strategy, symbol=symbol, interval=interval,
        days=days, initial_equity=equity, leverage=leverage,
    )
    return await engine.run()


async def multi_backtest(
    strategy: str = None,
    symbols: List[str] = None,
    interval: str = "1h",
    days: int = 30,
    initial_equity: float = 1000.0,
    leverage: int = None,
    max_concurrent: int = 4,
) -> MultiBacktestReport:
    """
    多币种批量回测

    Args:
        strategy: 策略名(默认 dual_ma)
        symbols: 币种列表(默认从 trading_pairs.json 读)
        interval: K线周期
        days: 回测天数
        initial_equity: 每币种初始资金
        leverage: 杠杆(默认从 config)
        max_concurrent: 最大并发(限流 binance-cli 调用)

    Returns:
        MultiBacktestReport
    """
    strategy = strategy or "dual_ma"
    leverage = leverage or CONFIG.trading.leverage

    if symbols is None:
        symbols = load_pairs()
        if not symbols:
            log.warning("交易对池为空,使用默认 BTCUSDT")
            symbols = ["BTCUSDT"]

    # 限制并发
    sem = asyncio.Semaphore(max_concurrent)

    async def bounded(symbol):
        async with sem:
            try:
                return symbol, await _run_one(
                    symbol, strategy, interval, days, initial_equity, leverage
                )
            except Exception as e:
                log.error(f"{symbol} 回测失败: {e}")
                return symbol, e

    started = time.time()
    log.info(f"🚀 多币种回测: {len(symbols)} 币种, 策略={strategy}, 周期={interval}, 天数={days}")

    tasks = [bounded(s) for s in symbols]
    results = await asyncio.gather(*tasks)

    report = MultiBacktestReport(
        strategy=strategy, interval=interval, days=days,
        initial_equity_per_symbol=initial_equity, leverage=leverage,
    )
    report.duration_sec = time.time() - started

    for sym, r in results:
        if isinstance(r, Exception):
            report.errors[sym] = str(r)
        else:
            report.per_symbol[sym] = r

    return report


# ==================== 单独运行 ====================
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="多币种回测")
    p.add_argument("--strategy", default="dual_ma", help="策略名")
    p.add_argument("--days", type=int, default=7, help="回测天数")
    p.add_argument("--interval", default="1h", help="K线周期")
    p.add_argument("--equity", type=float, default=1000.0, help="每币种初始")
    p.add_argument("--symbols", nargs="*", default=None, help="指定币种(默认全池)")
    p.add_argument("--top", type=int, default=5, help="用池子前 N 币种(避免太长)")
    p.add_argument("--concurrent", type=int, default=4, help="最大并发")
    args = p.parse_args()

    symbols = args.symbols
    if symbols is None:
        all_pairs = load_pairs()
        symbols = all_pairs[:args.top] if all_pairs else ["BTCUSDT"]

    report = asyncio.run(multi_backtest(
        strategy=args.strategy,
        symbols=symbols,
        interval=args.interval,
        days=args.days,
        initial_equity=args.equity,
        max_concurrent=args.concurrent,
    ))
    print(report.summary())

    # 同时导出报告
    from src.backtest.report import save_report
    paths = save_report(
        type(report.per_symbol.get("BTCUSDT")) if report.per_symbol else None,
        # 上面只是占位,实际用法见下
    ) if False else None
