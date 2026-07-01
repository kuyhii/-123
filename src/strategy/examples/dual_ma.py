"""
src/strategy/examples/dual_ma.py - 双均线示例策略

金叉买入,死叉卖出。可用作模板。
"""
import sys
from pathlib import Path
from typing import Optional

# 让 `python src/strategy/examples/dual_ma.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.data.models import Kline, Signal, Side
from src.strategy.base import Strategy


class DualMAStrategy(Strategy):
    """双均线策略"""

    name = "DualMA"

    def __init__(self, fast: int = 5, slow: int = 20, quantity: float = 0.001):
        super().__init__(fast=fast, slow=slow, quantity=quantity)
        self.fast = fast
        self.slow = slow
        self.qty = quantity
        self.position_side: Optional[Side] = None

    def _ma(self, period: int) -> Optional[float]:
        if len(self.klines) < period:
            return None
        closes = [k.close for k in self.klines[-period:]]
        return sum(closes) / period

    def on_kline_closed(self, kline: Kline) -> Optional[Signal]:
        fast_now = self._ma(self.fast)
        slow_now = self._ma(self.slow)
        if fast_now is None or slow_now is None:
            return None

        # 算上一根的 MA
        prev = self.klines[-2] if len(self.klines) >= 2 else None
        if not prev:
            return None
        saved = self.klines.pop()
        fast_prev = self._ma(self.fast)
        slow_prev = self._ma(self.slow)
        self.klines.append(saved)
        if fast_prev is None or slow_prev is None:
            return None

        # 金叉: 上一根 fast <= slow, 当前 fast > slow
        if fast_prev <= slow_prev and fast_now > slow_now:
            if self.position_side != Side.BUY:
                self.position_side = Side.BUY
                return Signal(
                    symbol=kline.symbol, side=Side.BUY, quantity=self.qty,
                    reason=f"Golden Cross MA{self.fast}/MA{self.slow}",
                )
        # 死叉
        elif fast_prev >= slow_prev and fast_now < slow_now:
            if self.position_side != Side.SELL:
                self.position_side = Side.SELL
                return Signal(
                    symbol=kline.symbol, side=Side.SELL, quantity=self.qty,
                    reduce_only=self.position_side is not None,
                    reason=f"Death Cross MA{self.fast}/MA{self.slow}",
                )
        return None


# 单独运行测试
if __name__ == "__main__":
    import random
    print("🔍 DualMA 策略测试(用模拟数据)\n")

    s = DualMAStrategy(fast=3, slow=5, quantity=0.01)

    # 生成 30 根假 K 线(模拟趋势)
    base = 100
    klines = []
    for i in range(30):
        base += random.gauss(0, 2)
        klines.append(Kline(
            open_time=i * 60000,
            open=base, high=base + 1, low=base - 1, close=base,
            volume=100, close_time=(i + 1) * 60000, symbol="TEST"
        ))

    for k in klines:
        sig = s.feed(k, closed=True)
        if sig:
            print(f"  K{i}: {sig.reason}")

    print(f"\n总信号数: {len(s.signals)}")
    print("🎉 DualMA 模拟测试完成")
