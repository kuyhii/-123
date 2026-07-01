# 策略开发指南

## 策略接口

所有策略必须实现 `Strategy` 抽象基类:

```python
from abc import ABC, abstractmethod
from typing import Optional
from src.data.market_data import Kline, OrderBook
from src.strategy.signal import Signal, Side

class Strategy(ABC):
    """策略基类"""

    name: str = "Unnamed"

    @abstractmethod
    async def on_kline(self, kline: Kline) -> Optional[Signal]:
        """
        接收 K 线(已收盘)
        返回 Signal 表示开/平仓信号,None 表示不动
        """
        pass

    @abstractmethod
    async def on_orderbook(self, ob: OrderBook) -> Optional[Signal]:
        """接收深度快照"""
        pass

    async def on_init(self) -> None:
        """策略启动钩子"""
        pass

    async def on_stop(self) -> None:
        """策略停止钩子"""
        pass
```

## Signal 信号

```python
from dataclasses import dataclass
from enum import Enum

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"

class SignalType(Enum):
    OPEN_LONG = "OPEN_LONG"
    OPEN_SHORT = "OPEN_SHORT"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"

@dataclass
class Signal:
    symbol: str
    side: Side
    type: SignalType
    quantity: float        # 数量
    price: Optional[float] = None   # None = 市价
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""       # 调试用,记录为什么产生信号
```

## 示例:双均线策略

```python
import pandas as pd
from src.strategy.base import Strategy
from src.strategy.signal import Signal, Side, SignalType

class DualMAStrategy(Strategy):
    name = "DualMA"

    def __init__(self, fast: int = 5, slow: int = 20, qty: float = 0.001):
        self.fast = fast
        self.slow = slow
        self.qty = qty
        self.klines: list = []
        self.position_side: Optional[Side] = None

    async def on_kline(self, kline) -> Optional[Signal]:
        self.klines.append(kline)
        if len(self.klines) < self.slow + 1:
            return None

        df = pd.DataFrame([{
            'time': k.time, 'close': k.close
        } for k in self.klines[-self.slow - 1:]])

        fast_ma = df['close'].rolling(self.fast).mean()
        slow_ma = df['close'].rolling(self.slow).mean()

        # 金叉: 快线上穿慢线
        if fast_ma.iloc[-2] <= slow_ma.iloc[-2] and fast_ma.iloc[-1] > slow_ma.iloc[-1]:
            if self.position_side != Side.BUY:
                self.position_side = Side.BUY
                return Signal(
                    symbol=kline.symbol, side=Side.BUY,
                    type=SignalType.OPEN_LONG, quantity=self.qty, reason="Golden Cross"
                )

        # 死叉: 快线下穿慢线
        if fast_ma.iloc[-2] >= slow_ma.iloc[-2] and fast_ma.iloc[-1] < slow_ma.iloc[-1]:
            if self.position_side != Side.SELL:
                self.position_side = Side.SELL
                return Signal(
                    symbol=kline.symbol, side=Side.SELL,
                    type=SignalType.OPEN_SHORT, quantity=self.qty, reason="Death Cross"
                )

        return None
```

## 回测

`src/backtest/engine.py` 提供回测框架:

```python
from src.backtest.engine import BacktestEngine
from src.strategy.examples.dual_ma import DualMAStrategy

engine = BacktestEngine(
    strategy=DualMAStrategy(fast=5, slow=20),
    symbol="BTCUSDT",
    interval="1h",
    start_time="2024-01-01",
    end_time="2024-12-31",
    initial_balance=10000,
    leverage=10,
)

result = await engine.run()
print(f"收益率: {result.total_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
print(f"胜率: {result.win_rate:.2%}")
```

## 调试技巧

### 1. 单独测试策略

```python
# 假数据测试
from src.strategy.examples.dual_ma import DualMAStrategy
import asyncio

async def test():
    strat = DualMAStrategy()
    await strat.on_init()
    for kline in fake_klines:  # 100 根假 K 线
        sig = await strat.on_kline(kline)
        if sig:
            print(f"Signal: {sig}")

asyncio.run(test())
```

### 2. 启动时只跑回测模式

```bash
python src/main.py --mode backtest --strategy dual_ma --symbol BTCUSDT --days 365
```

### 3. 启动时只跑模拟盘

```bash
python src/main.py --mode paper --strategy dual_ma --symbol BTCUSDT
```

## 风险提示

⚠️ 任何策略都要在 testnet / demo / 模拟盘充分测试后再考虑实盘。
**永远不要在没充分验证前用真金白银。**
