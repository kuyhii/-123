# Architecture

## 概述

量化合约交易系统采用 **L0 ~ L5 六层架构**,自下而上分别为适配层、数据层、账户层、执行层、风控层、策略层。

每一层只依赖下一层,层与层之间通过**接口/事件**解耦,便于测试和替换。

---

## 详细分层

### L0: Adapter (适配层) - `src/adapter/`

**职责**: 封装 `binance-cli` 的所有调用,统一命令、超时、重试、错误处理。

**关键模块**:
- `binance_cli.py` - CLI 调用的 Python 封装
- `errors.py` - 统一异常体系
- `retry.py` - 重试装饰器(429 限流自动 backoff)

**核心接口**:
```python
class BinanceCLI:
    async def request(self, method: str, endpoint: str, **params) -> dict
    async def futures_usds(self, command: str, **params) -> dict
    async def futures_usds_streams(self, command: str, **params) -> AsyncIterator
```

---

### L1: Data (数据层) - `src/data/`

**职责**: 提供行情和历史数据,WebSocket 实时推送 + REST 历史查询。

**关键模块**:
- `market_data.py` - REST 行情查询(K线、深度、ticker)
- `ws_kline.py` - K线 WebSocket 订阅
- `ws_depth.py` - 深度 WebSocket 订阅
- `ws_mark_price.py` - Mark Price + Funding Rate
- `historical.py` - 历史数据下载与持久化

**核心接口**:
```python
class MarketData:
    async def kline(self, symbol: str, interval: str, limit: int) -> List[Kline]
    async def orderbook(self, symbol: str, limit: int) -> OrderBook
    async def mark_price(self, symbol: str) -> MarkPrice
    async def funding_rate(self, symbol: str) -> FundingRate

class KlineStream:
    async def subscribe(self, symbol: str, interval: str, callback)
```

---

### L2: Account (账户层) - `src/account/`

**职责**: 维护本地账户状态,与 user-data-stream 同步。

**关键模块**:
- `balance.py` - USDT 余额 / 可用保证金
- `position.py` - 当前持仓(单向/双向)
- `orders.py` - 挂单 / 历史订单
- `user_data_stream.py` - user-data WS 同步

**核心接口**:
```python
class Account:
    async def balance(self) -> Balance
    async def position(self, symbol: str) -> Optional[Position]
    async def open_orders(self, symbol: str = None) -> List[Order]
    async def set_leverage(self, symbol: str, leverage: int)
    async def set_margin_type(self, symbol: str, margin_type: str)
```

---

### L3: Executor (执行层) - `src/executor/`

**职责**: 把策略信号转化为实际订单,处理下单/撤单/改单。

**关键模块**:
- `order_manager.py` - 订单生命周期管理
- `order_router.py` - 智能路由(限价/市价/算法单)
- `algo_orders.py` - TP/SL 算法单

**核心接口**:
```python
class OrderRouter:
    async def market_order(self, symbol, side, quantity, reduce_only=False)
    async def limit_order(self, symbol, side, quantity, price, time_in_force='GTC')
    async def stop_market(self, symbol, side, quantity, stop_price)
    async def take_profit(self, symbol, side, quantity, tp_price)
    async def cancel_order(self, symbol, order_id)
    async def cancel_all(self, symbol)
```

---

### L4: Risk (风控层) - `src/risk/`

**职责**: 在下单前 / 持仓中持续校验,异常情况自动减仓或停机。

**关键模块**:
- `position_limit.py` - 单仓位上限
- `loss_limit.py` - 日内亏损熔断
- `leverage_check.py` - 杠杆检查
- `drawdown_check.py` - 回撤监控

**核心接口**:
```python
class RiskManager:
    def check_signal(self, signal: Signal) -> RiskCheck
    def check_position(self, position: Position) -> RiskCheck
    def on_fill(self, fill: Fill) -> None
    def daily_pnl(self) -> float
```

**风控规则(可配置)**:
- `MAX_POSITION_SIZE_PCT`: 单仓位占账户净值最大比例(默认 30%)
- `MAX_DAILY_LOSS_PCT`: 日内最大亏损熔断(默认 10%)
- `STOP_LOSS_PCT`: 默认止损比例(默认 2%)
- `MAX_LEVERAGE`: 最大杠杆倍数
- `BLACKLIST_SYMBOLS`: 禁止交易的币种

---

### L5: Strategy (策略层) - `src/strategy/`

**职责**: 接收行情,生成交易信号。

**策略接口**:
```python
class Strategy(ABC):
    @abstractmethod
    def on_kline(self, kline: Kline) -> Optional[Signal]:
        """每根 K 线触发"""
        pass

    @abstractmethod
    def on_orderbook(self, ob: OrderBook) -> Optional[Signal]:
        """深度变化触发"""
        pass
```

**内置策略**:
- `trend_following.py` - 双均线 / EMA 趋势
- `mean_reversion.py` - 布林带均值回归
- `grid.py` - 现货网格(后续)
- `funding_arb.py` - 资金费率套利(后续)

---

## 数据流

```
   ┌─────────────┐
   │ binance-cli │
   └──────┬──────┘
          │
    L0 Adapter
          │
   ┌──────▼──────┐         ┌──────────┐
   │  L1 Data    │────────▶│ Strategy │ (L5)
   └──────┬──────┘         └─────┬────┘
          │                      │ Signal
          │                      ▼
   ┌──────▼──────┐         ┌──────────┐
   │ L2 Account  │◀────────│   L3     │
   └──────┬──────┘         │ Executor │
          │                 └─────┬────┘
          │                       │ Order
          │                       ▼
          │                 ┌──────────┐
          └────────────────▶│   L4     │
                            │   Risk   │
                            └──────────┘
```

---

## 并发模型

- **Asyncio**: 所有 I/O 异步
- **事件循环**: 单进程 asyncio 事件循环
- **WS 长连接**: K线 / 深度 / user-data 三个独立流
- **CPU 密集**(指标计算): 用 `loop.run_in_executor` 放线程池

---

## 部署

- **本地开发**: 直接 `python src/main.py`
- **云服务器**: systemd / supervisor
- **Docker**: 后续添加 Dockerfile
