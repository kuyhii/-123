"""
Demo 模式:验证环境配置 + 拉取行情做基本检查
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def run_demo(symbol: str = "BTCUSDT"):
    """跑通 demo 流程"""
    print(f"\n📊 Demo 模式 - 交易对: {symbol}\n")

    # 1. 检查 binance-cli 是否安装
    from hermes_tools import terminal
    print("1️⃣  检查 binance-cli...")
    result = await asyncio.to_thread(terminal, "binance-cli --version 2>&1")
    if result["exit_code"] != 0:
        print("❌ binance-cli 未安装")
        print("   请运行: npm install -g @binance/binance-cli")
        return
    print(f"   ✅ {result['output'].strip()}\n")

    # 2. 测试连通性
    print("2️⃣  测试连接 Binance Futures...")
    result = await asyncio.to_thread(
        terminal, "binance-cli futures-usds test-connectivity 2>&1"
    )
    if result["exit_code"] == 0:
        print("   ✅ 连接成功\n")
    else:
        print(f"   ⚠️  {result['output'].strip()}\n")

    # 3. 拉取行情
    print(f"3️⃣  拉取 {symbol} 行情...")
    result = await asyncio.to_thread(
        terminal,
        f"binance-cli futures-usds ticker24hr-price-change-statistics --symbol {symbol} 2>&1"
    )
    if result["exit_code"] == 0:
        try:
            data = json.loads(result["output"])
            print(f"   ✅ 最新价:     {data.get('lastPrice', 'N/A')}")
            print(f"   ✅ 24h 涨跌:   {data.get('priceChangePercent', 'N/A')}%")
            print(f"   ✅ 24h 最高:   {data.get('highPrice', 'N/A')}")
            print(f"   ✅ 24h 最低:   {data.get('lowPrice', 'N/A')}")
            print(f"   ✅ 24h 成交量: {data.get('volume', 'N/A')}")
        except json.JSONDecodeError:
            print(f"   输出: {result['output'][:200]}")
    else:
        print(f"   ❌ {result['output'][:200]}")

    # 4. 拉取 K 线
    print(f"\n4️⃣  拉取 {symbol} 1h K 线 (最近 5 根)...")
    result = await asyncio.to_thread(
        terminal,
        f"binance-cli futures-usds kline-candlestick-data --symbol {symbol} --interval 1h --limit 5 2>&1"
    )
    if result["exit_code"] == 0:
        try:
            data = json.loads(result["output"])
            if isinstance(data, list) and data:
                print("   ✅ K 线数据:")
                for k in data:
                    # K 线: [openTime, open, high, low, close, volume, ...]
                    print(f"      {k[0]}  O={k[1]} H={k[2]} L={k[3]} C={k[4]} V={k[5]}")
        except json.JSONDecodeError:
            print(f"   输出: {result['output'][:200]}")
    else:
        print(f"   ❌ {result['output'][:200]}")

    print("\n🎉 Demo 跑通!")
    print("\n下一步:")
    print("  - 配置 API key: binance-cli profile create ...")
    print("  - 跑回测:        python src/main.py --mode backtest --days 365")
    print("  - 跑模拟盘:      python src/main.py --mode paper")


if __name__ == "__main__":
    asyncio.run(run_demo())
