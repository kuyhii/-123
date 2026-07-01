"""
src/strategy/examples/multi_tf_trend.py - 多周期趋势策略

设计:
- 主时间框架(3m)做开平仓信号(快速反应)
- 长周期(5m)做趋势确认(过滤震荡)
- 三种状态:
  * 主多 + 长大多 = 强多 (开多)
  * 主多 + 长空   = 弱多 (不开)
  * 主空 + 长大空 = 强空 (开空)
  * 主空 + 长多   = 弱空 (不开)

使用 EMA(快线 vs 慢线)判断方向。
"""
import sys
from pathlib import Path
from typing import Optional, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.data.models import Kline, Signal, Side
from src.strategy.base import Strategy
from src.strategy.factory import register


@register("multi_tf_trend")
class MultiTFTrendStrategy(Strategy):
    """
    多时间框架趋势策略

    Args:
        fast: 短 EMA 周期
        slow: 长 EMA 周期
        fast_interval: 主时间框架(快速信号)
        slow_interval: 长周期(趋势确认)
        quantity: 下单数量
    """

    name = "MultiTFTrend"

    def __init__(self, fast: int = 5, slow: int = 10,
                 fast_interval: str = "3m", slow_interval: str = "5m",
                 quantity: float = 0.001):
        super().__init__(fast=fast, slow=slow, fast_interval=fast_interval,
                         slow_interval=slow_interval, quantity=quantity)
        self.fast = fast
        self.slow = slow
        self.fast_interval = fast_interval
        self.slow_interval = slow_interval
        self.qty = quantity

        # 不同时间框架独立存储 K 线
        self.klines_fast: List[Kline] = []
        self.klines_slow: List[Kline] = []

        # 当前趋势状态: +1 多 / -1 空 / 0 无
        self.fast_trend: int = 0
        self.slow_trend: int = 0
        self.position_side: Optional[Side] = None

    def _ema(self, values: List[float], period: int) -> Optional[float]:
        if len(values) < period:
            return None
        k = 2.0 / (period + 1)
        ema_val = sum(values[:period]) / period
        for v in values[period:]:
            ema_val = v * k + ema_val * (1 - k)
        return ema_val

    def _update_trend(self, interval: str) -> int:
        """更新指定时间框架的趋势状态"""
        klines = self.klines_fast if interval == self.fast_interval else self.klines_slow
        if len(klines) < self.slow:
            return 0
        closes = [k.close for k in klines]
        fast_ema = self._ema(closes, self.fast)
        slow_ema = self._ema(closes, self.slow)
        if fast_ema is None or slow_ema is None:
            return 0
        return 1 if fast_ema > slow_ema else -1

    def on_kline_closed(self, kline: Kline) -> Optional[Signal]:
        """
        K线收盘时被调用。
        - 短周期 K线:更新 fast_trend
        - 长周期 K线:更新 slow_trend
        - 当任一框架趋势变化,且双框架方向一致时,生成信号
        """
        if kline.interval == self.fast_interval:
            self.klines_fast.append(kline)
            self.fast_trend = self._update_trend(self.fast_interval)
        elif kline.interval == self.slow_interval:
            self.klines_slow.append(kline)
            self.slow_trend = self._update_trend(self.slow_interval)
        else:
            # 不识别的 interval,忽略
            return None

        # 需要双框架都有趋势
        if self.fast_trend == 0 or self.slow_trend == 0:
            return None

        # 趋势不一致 → 不开仓(震荡市过滤)
        if self.fast_trend != self.slow_trend:
            return None

        # 一致 → 检查仓位状态
        if self.fast_trend == 1 and self.position_side != Side.BUY:
            self.position_side = Side.BUY
            return Signal(
                symbol=kline.symbol, side=Side.BUY, quantity=self.qty,
                reason=f"双框架共振多(fast={self.fast_interval}↑ slow={self.slow_interval}↑)",
            )
        if self.fast_trend == -1 and self.position_side != Side.SELL:
            self.position_side = Side.SELL
            return Signal(
                symbol=kline.symbol, side=Side.SELL, quantity=self.qty,
                reduce_only=self.position_side is not None,
                reason=f"双框架共振空(fast={self.fast_interval}↓ slow={self.slow_interval}↓)",
            )
        return None


# ==================== 单独测试 ====================
if __name__ == "__main__":
    print("🔍 MultiTFTrend 策略测试(模拟)\n")

    s = MultiTFTrendStrategy(fast=3, slow=5, quantity=0.01)

    # 模拟两个时间框架的 K 线流
    # 交替喂入
    for i in range(30):
        # 短周期(3m)
        fast_close = 100 + (i * 1.5 if i < 20 else -i * 2)
        s.klines_fast.append(Kline(
            open_time=i * 180000, open=fast_close, high=fast_close + 0.5,
            low=fast_close - 0.5, close=fast_close, volume=100,
            close_time=(i + 1) * 180000, symbol="TESTUSDT", interval="3m"
        ))
        s.feed(s.klines_fast[-1], closed=True)

        # 长周期(5m) 慢一点
        if i % 2 == 0:
            slow_close = 100 + (i * 1.5 if i < 20 else -i * 2)
            s.klines_slow.append(Kline(
                open_time=i * 300000, open=slow_close, high=slow_close + 0.5,
                low=slow_close - 0.5, close=slow_close, volume=100,
                close_time=(i + 1) * 300000, symbol="TESTUSDT", interval="5m"
            ))
            s.feed(s.klines_slow[-1], closed=True)

    print(f"信号数: {len(s.signals)}")
    for sig in s.signals:
        print(f"  {sig}")
    print("\n🎉 MultiTFTrend 模拟测试完成")
