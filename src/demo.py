"""
src/demo.py - Demo 模式

1. 检查环境(binance-cli、.env、Python 包)
2. 拉 BTC 实时行情
3. 拉 K 线 + 计算 MA20、RSI
4. 显示账户余额(如有 API key)
5. 拉资金费率
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger
from src.config import CONFIG
from src.adapter.binance_cli import _is_installed, BINANCE_CLI
from src.data.market_data import MarketData, sma, rsi
from src.data.models import Kline

log = get_logger("demo")


async def run_demo(symbol: str = "BTCUSDT"):
    print(f"\n📊 Demo 模式 - 交易对: {symbol}\n")

    # 1. 环境检查
    print("1️⃣  环境检查")
    if not _is_installed():
        print("   ❌ binance-cli 未安装")
        print("      请运行: npm install -g @binance/binance-cli")
        return
    print(f"   ✅ binance-cli: {BINANCE_CLI}")
    print(f"   ✅ API key: {'已配置' if CONFIG.has_credentials else '⚠️  未配置(仅公开数据可用)'}")
    print(f"   ✅ 环境: {CONFIG.binance.env}\n")

    # 2. 实时行情
    print(f"2️⃣  {symbol} 实时行情")
    try:
        t = await MarketData.ticker(symbol)
        arrow = "📈" if t.price_change_pct >= 0 else "📉"
        print(f"   {arrow} 最新价:     ${t.last_price:,.2f}")
        print(f"      24h 涨跌:   {t.price_change_pct:+.2f}% (${t.price_change:+.2f})")
        print(f"      24h 最高:   ${t.high:,.2f}")
        print(f"      24h 最低:   ${t.low:,.2f}")
        print(f"      24h 成交量: {t.volume:,.2f} {symbol[:-4]}\n")
    except Exception as e:
        print(f"   ❌ {e}\n")

    # 3. K 线 + 指标
    print(f"3️⃣  {symbol} 1h K线 (100 根) + 技术指标")
    try:
        klines = await MarketData.kline(symbol, "1h", limit=100)
        closes = [k.close for k in klines]
        ma5 = sma(closes, 5)
        ma20 = sma(closes, 20)
        rsi14 = rsi(closes, 14)

        print(f"   📊 拿到 {len(klines)} 根 K 线")
        print(f"      最近 1 根: O={klines[-1].open} H={klines[-1].high} L={klines[-1].low} C={klines[-1].close}")
        if ma5:   print(f"      MA5:   {ma5:,.2f}")
        if ma20:  print(f"      MA20:  {ma20:,.2f}")
        if rsi14: print(f"      RSI14: {rsi14:.2f}")

        if ma5 and ma20:
            if ma5 > ma20:
                print(f"      趋势:    📈 短期 MA5 > MA20 (多头)")
            else:
                print(f"      趋势:    📉 短期 MA5 < MA20 (空头)")
        if rsi14:
            if rsi14 > 70:   print(f"      RSI:     ⚠️  超买区")
            elif rsi14 < 30: print(f"      RSI:     ⚠️  超卖区")
            else:            print(f"      RSI:     正常")
        print()
    except Exception as e:
        print(f"   ❌ {e}\n")

    # 4. 资金费率
    print(f"4️⃣  {symbol} Mark Price + 资金费率")
    try:
        mp = await MarketData.mark_price(symbol)
        print(f"      Mark Price:  ${mp.mark_price:,.2f}")
        print(f"      Index Price: ${mp.index_price:,.2f}")
        print(f"      资金费率:    {mp.funding_rate*100:+.4f}%")
        if mp.funding_rate > 0:
            print(f"      → 多头付给空头")
        else:
            print(f"      → 空头付给多头")
        print()
    except Exception as e:
        print(f"   ❌ {e}\n")

    # 5. 账户余额(如有 API key)
    if CONFIG.has_credentials:
        print(f"5️⃣  账户余额({CONFIG.binance.env})")
        from src.account.account import Account
        acc = Account()
        try:
            await acc.refresh_balances()
            usdt = acc.usdt_balance()
            print(f"      USDT 余额:     {usdt.balance:,.2f}")
            print(f"      可用余额:      {usdt.available_balance:,.2f}")
            print(f"      未实现盈亏:    {usdt.unrealized_pnl:,.2f}")
            print(f"      总权益:        {acc.total_equity():,.2f}")
        except Exception as e:
            print(f"      ❌ {e}")
    else:
        print(f"5️⃣  账户余额 - 跳过(未配置 API key)")

    print("\n" + "=" * 60)
    print("🎉 Demo 跑通!")
    print("=" * 60)
    print("\n下一步:")
    print("  - 配置 API key:  copy .env.example .env,然后编辑 .env")
    print("  - 创建 profile:  binance-cli profile create --name default --api-key <KEY> --api-secret <SECRET> --env demo")
    print("  - 跑回测:        python src/main.py --mode backtest --days 90")
    print("  - 跑模拟盘:      python src/main.py --mode paper")
    print("  - 单模块测试:    python src/data/market_data.py")


if __name__ == "__main__":
    asyncio.run(run_demo())
