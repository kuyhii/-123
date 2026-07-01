"""
src/data/market_data.py - L1 数据层(公开行情 REST)

提供行情数据查询接口,不需要 API key。
"""
import asyncio
from typing import List, Optional

from src.adapter.binance_cli import FuturesUSDS, call
from src.data.models import Kline, OrderBook, Ticker24h, MarkPrice
from src.logger import get_logger

log = get_logger("data.market")


class MarketData:
    """公开行情数据"""

    @staticmethod
    async def kline(symbol: str, interval: str, limit: int = 100) -> List[Kline]:
        """
        获取 K 线

        interval: 1s | 1m | 3m | 5m | 15m | 30m | 1h | 2h | 4h | 6h | 8h | 12h | 1d | 3d | 1w | 1M
        """
        raw = await FuturesUSDS.kline(symbol, interval, limit)
        return [Kline.from_binance(k, symbol) for k in raw]

    @staticmethod
    async def orderbook(symbol: str, limit: int = 20) -> OrderBook:
        raw = await FuturesUSDS.orderbook(symbol, limit)
        return OrderBook.from_binance(raw)

    @staticmethod
    async def ticker(symbol: str) -> Ticker24h:
        raw = await FuturesUSDS.ticker_24h(symbol)
        return Ticker24h.from_binance(raw)

    @staticmethod
    async def mark_price(symbol: str) -> MarkPrice:
        raw = await FuturesUSDS.mark_price(symbol)
        if isinstance(raw, list) and raw:
            return MarkPrice.from_binance(raw[0])
        return MarkPrice.from_binance(raw)

    @staticmethod
    async def funding_rate(symbol: str, limit: int = 10) -> list:
        """获取资金费率历史"""
        return await FuturesUSDS.funding_rate(symbol, limit)

    @staticmethod
    async def exchange_info() -> dict:
        """交易所信息(交易对规则)"""
        return await call("futures-usds", "exchange-information")


# ==================== 简单技术指标(手写,不依赖 pandas) ====================

def sma(values: List[float], period: int) -> Optional[float]:
    """简单移动平均线(最后 N 个值的平均)"""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def sma_series(values: List[float], period: int) -> List[Optional[float]]:
    """完整 SMA 序列"""
    result = []
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(values[i - period + 1:i + 1]) / period)
    return result


def ema(values: List[float], period: int) -> Optional[float]:
    """指数移动平均(单值)"""
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    # 初始用 SMA
    ema_val = sum(values[:period]) / period
    for v in values[period:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


def rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """RSI 指标(单值)"""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(-diff)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ==================== 单独运行测试 ====================
if __name__ == "__main__":
    """单独跑这个文件:测试 L1 数据层"""
    import sys

    print("🔍 L1 数据层测试\n")

    async def test():
        symbol = "BTCUSDT"

        # 1. Ticker
        print(f"1️⃣  {symbol} 24h ticker ...")
        try:
            t = await MarketData.ticker(symbol)
            print(f"   ✅ 最新价: {t.last_price}, 24h%: {t.price_change_pct}%\n")
        except Exception as e:
            print(f"   ❌ {e}\n")

        # 2. K线 + 指标
        print(f"2️⃣  {symbol} 1h K线 (100 根) + MA20 ...")
        try:
            klines = await MarketData.kline(symbol, "1h", limit=100)
            closes = [k.close for k in klines]
            ma20 = sma(closes, 20)
            last_rsi = rsi(closes, 14)
            print(f"   ✅ 拿到 {len(klines)} 根, MA20={ma20:.2f}, RSI14={last_rsi:.2f}\n")
        except Exception as e:
            print(f"   ❌ {e}\n")

        # 3. 深度
        print(f"3️⃣  {symbol} 深度 (5 档) ...")
        try:
            ob = await MarketData.orderbook(symbol, limit=5)
            print(f"   ✅ 买1: {ob.best_bid}, 卖1: {ob.best_ask}, 价差: {ob.spread_pct:.4f}%\n")
        except Exception as e:
            print(f"   ❌ {e}\n")

        # 4. 资金费率
        print(f"4️⃣  {symbol} 资金费率 ...")
        try:
            mp = await MarketData.mark_price(symbol)
            print(f"   ✅ Mark: {mp.mark_price}, Funding: {mp.funding_rate*100:.4f}%\n")
        except Exception as e:
            print(f"   ❌ {e}\n")

    asyncio.run(test())
    print("🎉 L1 测试完成")
