"""
量化合约交易系统 - 主入口

用法:
    python src/main.py --mode demo                    # 跑通 demo
    python src/main.py --mode backtest --days 365     # 回测
    python src/main.py --mode paper --strategy dual_ma # 模拟盘
    python src/main.py --mode live                    # 实盘(危险!)
"""
import argparse
import asyncio
import sys
from pathlib import Path

# 让脚本能以 `python src/main.py` 直接运行
sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_args():
    p = argparse.ArgumentParser(description="量化合约交易系统")
    p.add_argument("--mode", choices=["demo", "backtest", "paper", "live"],
                   default="demo", help="运行模式")
    p.add_argument("--symbol", default="BTCUSDT", help="交易对")
    p.add_argument("--strategy", default="dual_ma", help="策略名")
    p.add_argument("--days", type=int, default=90, help="回测天数")
    p.add_argument("--interval", default="1h", help="K 线周期")
    return p.parse_args()


async def main():
    args = parse_args()

    print("=" * 60)
    print(f"  量化合约交易系统 v0.1.0")
    print(f"  Mode:    {args.mode}")
    print(f"  Symbol:  {args.symbol}")
    print(f"  Strategy:{args.strategy}")
    print("=" * 60)

    if args.mode == "demo":
        from src.demo import run_demo
        await run_demo(args.symbol)
    elif args.mode == "backtest":
        print("⚠️  回测功能开发中...")
        # from src.backtest.engine import run_backtest
        # await run_backtest(args)
    elif args.mode == "paper":
        print("⚠️  模拟盘功能开发中...")
    elif args.mode == "live":
        # 强制要求用户输入 CONFIRM
        print()
        print("⚠️⚠️⚠️  实盘交易模式  ⚠️⚠️⚠️")
        print("实盘交易将使用真实资金,请确保:")
        print("  1. API key 已配置且仅有 futures 权限")
        print("  2. 已在 demo/testnet 充分测试")
        print("  3. 资金量在可承受亏损范围内")
        print()
        confirm = input("输入 CONFIRM 继续: ")
        if confirm.strip() != "CONFIRM":
            print("❌ 已取消")
            return
        print("✅ 启动实盘...")


if __name__ == "__main__":
    asyncio.run(main())
