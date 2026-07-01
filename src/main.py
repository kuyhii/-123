"""
src/main.py - 主入口

分发不同运行模式:
- demo:      验证环境
- backtest:  历史回测
- paper:     模拟盘
- live:      实盘(危险)
- --refresh-pool:  从币安拉最新交易量前 30 币种池
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_args():
    p = argparse.ArgumentParser(
        description="量化合约交易系统 (Binance USDT Perpetual)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        "--mode", choices=["demo", "backtest", "paper", "live"],
        default="demo",
        help="""运行模式:
  demo      - 验证环境 + 拉行情(默认)
  backtest  - 历史数据回测
  paper     - 模拟盘(实时行情,不下单)
  live      - 实盘(危险!)""",
    )
    p.add_argument("--symbol", default=None, help="交易对(默认从 config 读)")
    p.add_argument("--strategy", default="dual_ma", help="策略名")
    p.add_argument("--days", type=int, default=90, help="回测天数")
    p.add_argument("--interval", default=None, help="K线周期(默认从 config 读)")
    p.add_argument("--profile", default=None, help="binance-cli profile 名")
    p.add_argument("--refresh-pairs", action="store_true",
                   help="从币安拉最新交易量前 40 交易对池")
    p.add_argument("--update-now", action="store_true",
                   help="立即刷新交易对池(同 --refresh-pairs)")
    p.add_argument("--scheduler", action="store_true",
                   help="启动后台调度器(每天 00:00 UTC 自动更新)")
    return p.parse_args()


async def run_demo(args):
    from src.demo import run_demo
    await run_demo(args.symbol or "BTCUSDT")


async def run_backtest(args):
    from src.strategy.examples.dual_ma import DualMAStrategy
    from src.backtest.engine import BacktestEngine
    from src.config import CONFIG

    symbol = args.symbol or CONFIG.trading.default_symbol
    interval = args.interval or "1h"
    print(f"\n📈 回测模式 - {symbol} {interval} {args.days} 天\n")
    print(f"策略: {args.strategy}")

    strategy = DualMAStrategy()  # TODO: 策略工厂
    engine = BacktestEngine(
        strategy=strategy, symbol=symbol, interval=interval,
        days=args.days, initial_equity=10000, leverage=CONFIG.trading.leverage,
    )
    result = await engine.run()
    print(result.summary())


async def run_paper(args):
    from src.config import CONFIG
    print("📝 模拟盘模式")
    print("⚠️  模拟盘功能开发中 - 暂时只能演示行情流")
    print("   完成后:策略在真实行情上跑,但所有 OrderRouter 调用 test_mode=True")

    # 临时演示:订阅 K 线流 5 根就退出
    from src.data.ws_kline import KlineStream
    symbol = args.symbol or CONFIG.trading.default_symbol
    interval = args.interval or "1m"
    stream = KlineStream(symbol, interval)
    count = 0
    try:
        async for k in stream.subscribe():
            status = "✅" if getattr(k, "is_closed", False) else "🔄"
            print(f"{status} {k.symbol} O={k.open} H={k.high} L={k.low} C={k.close}")
            count += 1
            if count >= 3:
                break
    except FileNotFoundError as e:
        print(f"❌ {e}")


async def run_live(args):
    print()
    print("⚠️⚠️⚠️  实盘交易模式  ⚠️⚠️⚠️")
    print("实盘将使用真实资金,所有操作不可撤销!")
    print()
    print("请确认:")
    print("  1. API key 已配置且仅有 futures 权限,无提现权限")
    print("  2. 已在 demo/testnet 充分测试")
    print("  3. 资金量在可承受亏损范围内")
    print()
    try:
        confirm = input("输入 CONFIRM 继续(其它任意键取消): ")
    except EOFError:
        confirm = ""
    if confirm.strip() != "CONFIRM":
        print("❌ 已取消")
        return
    print("✅ 启动实盘(开发中)...")


async def refresh_coin_pool():
    from src.strategy.trading_pairs import refresh_pairs
    from src.config import CONFIG
    print()
    print("🔄 刷新交易对池...")
    pool = refresh_pairs(top_n=CONFIG.pool.top_n)
    print(f"✅ {len(pool)} 个交易对已更新到 {CONFIG.pool.file}")


async def load_or_refresh_pairs() -> list:
    """
    启动时调用:按配置决定是直接用现成池子还是先刷新。
    返回交易对列表。
    """
    from src.strategy.trading_pairs import load_pairs, refresh_pairs
    from src.config import CONFIG

    pairs = load_pairs()
    if not pairs or CONFIG.pool.auto_update_on_start:
        if not pairs:
            log_msg = "交易对池文件不存在,启动时刷新"
        else:
            log_msg = f"配置要求启动时自动刷新(当前 {len(pairs)} 个)"
        from src.logger import get_logger
        log = get_logger("main")
        log.info(log_msg)
        pairs = refresh_pairs()
    return pairs


async def main():
    args = parse_args()

    from src.config import CONFIG
    from src.logger import get_logger
    log = get_logger("main")

    print("=" * 60)
    print(f"  量化合约交易系统 v0.3.0")
    print(f"  Mode:     {args.mode}")
    print(f"  Symbol:   {args.symbol or CONFIG.trading.default_symbol}")
    print(f"  Strategy: {args.strategy}")
    print(f"  Profile:  {args.profile or CONFIG.binance.profile}")
    print(f"  Env:      {CONFIG.binance.env}")
    print("=" * 60)
    log.info(CONFIG.summary())

    if args.mode == "demo":
        await run_demo(args)
    elif args.mode == "backtest":
        await run_backtest(args)
    elif args.mode == "paper":
        await run_paper(args)
    elif args.mode == "live":
        await run_live(args)

    if args.refresh_pairs or args.update_now:
        await refresh_coin_pool()

    if args.scheduler:
        from src.scheduler.pair_updater import run_forever
        print()
        print("⏰ 启动后台调度器(每天 00:00 UTC 更新池子)")
        print("   按 Ctrl+C 退出")
        try:
            run_forever()
        except KeyboardInterrupt:
            print("\n⏹️  调度器退出")


if __name__ == "__main__":
    asyncio.run(main())
