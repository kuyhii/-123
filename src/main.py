"""
src/main.py - 主入口

分发不同运行模式:
- demo:      验证环境
- backtest:  历史回测
- paper:     模拟盘
- live:      实盘(危险)
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
  live      - 实盘(危险!)"""
    )
    p.add_argument("--symbol", default=None, help="交易对(默认从 config 读)")
    p.add_argument("--strategy", default="dual_ma", help="策略名")
    p.add_argument("--days", type=int, default=90, help="回测天数")
    p.add_argument("--interval", default="1h", help="K线周期")
    p.add_argument("--profile", default=None, help="binance-cli profile 名")
    return p.parse_args()


async def run_demo(args):
    from src.demo import run_demo
    await run_demo(args.symbol or "BTCUSDT")


async def run_backtest(args):
    from src.strategy.examples.dual_ma import DualMAStrategy
    from src.backtest.engine import BacktestEngine
    from src.config import CONFIG

    symbol = args.symbol or CONFIG.trading.default_symbol
    print(f"\n📈 回测模式 - {symbol} {args.interval} {args.days} 天\n")
    print(f"策略: {args.strategy}")

    strategy = DualMAStrategy()  # TODO: 策略工厂
    engine = BacktestEngine(
        strategy=strategy, symbol=symbol, interval=args.interval,
        days=args.days, initial_equity=10000, leverage=CONFIG.trading.default_leverage,
    )
    result = await engine.run()
    print(result.summary())


async def run_paper(args):
    print("📝 模拟盘模式")
    print("⚠️  模拟盘功能开发中 - 暂时只能演示行情流")
    print("   完成后:策略在真实行情上跑,但所有 OrderRouter 调用 test_mode=True")

    # 临时演示:订阅 K 线流 5 根就退出
    from src.data.ws_kline import KlineStream
    stream = KlineStream(args.symbol or "BTCUSDT", args.interval)
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


async def main():
    args = parse_args()

    from src.config import CONFIG
    from src.logger import get_logger
    log = get_logger("main")

    print("=" * 60)
    print("  量化合约交易系统 v0.2.0")
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


if __name__ == "__main__":
    asyncio.run(main())
