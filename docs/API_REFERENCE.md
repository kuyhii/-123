# binance-cli API 速查

> 来源: [Binance Skills Hub](https://github.com/binance/binance-skills-hub) v1.2.0
> 完整文档: `skills/binance/binance/references/`

## 安装

```bash
npm install -g @binance/binance-cli
```

## 全局参数

| 参数 | 说明 |
|---|---|
| `--profile <name>` | 切换 profile,默认使用 active |
| `--recvWindow <ms>` | 接收窗口,最大 60000 |

## Profile 管理

```bash
# 创建(询问环境 prod/testnet/demo)
binance-cli profile create --name default --api-key <KEY> --api-secret <SECRET> --env demo

# 列表
binance-cli profile list

# 切换
binance-cli profile select --name default

# 当前
binance-cli profile view
```

## USDS-M 合约 (futures-usds) 常用命令

### 行情

```bash
# K 线
binance-cli futures-usds kline-candlestick-data --symbol BTCUSDT --interval 1h --limit 100

# 深度
binance-cli futures-usds order-book --symbol BTCUSDT --limit 20

# 24h ticker
binance-cli futures-usds ticker24hr-price-change-statistics --symbol BTCUSDT

# Mark Price
binance-cli futures-usds mark-price --symbol BTCUSDT

# 资金费率
binance-cli futures-usds get-funding-rate-history --symbol BTCUSDT --limit 10
```

### 账户

```bash
# 账户余额
binance-cli futures-usds futures-account-balance-v2

# 持仓
binance-cli futures-usds position-information-v2 --symbol BTCUSDT

# 调整杠杆
binance-cli futures-usds change-initial-leverage --symbol BTCUSDT --leverage 10

# 调整保证金模式
binance-cli futures-usds change-margin-type --symbol BTCUSDT --margin-type ISOLATED
```

### 下单

```bash
# 限价买单
binance-cli futures-usds new-order --symbol BTCUSDT --side BUY --type LIMIT \
    --quantity 0.001 --price 60000 --time-in-force GTC

# 市价卖单
binance-cli futures-usds new-order --symbol BTCUSDT --side SELL --type MARKET \
    --quantity 0.001 --reduce-only

# 限价单 + 测试(不下单)
binance-cli futures-usds test-order --symbol BTCUSDT --side BUY --type LIMIT \
    --quantity 0.001 --price 60000 --time-in-force GTC
```

### 算法单 (TP/SL)

```bash
# 止盈单
binance-cli futures-usds new-algo-order --algo-type TP --symbol BTCUSDT \
    --side SELL --type TAKE_PROFIT --quantity 0.001 --trigger-price 70000

# 止损单
binance-cli futures-usds new-algo-order --algo-type STOP --symbol BTCUSDT \
    --side SELL --type STOP_MARKET --quantity 0.001 --trigger-price 55000
```

### 撤单

```bash
# 撤销单笔
binance-cli futures-usds cancel-order --symbol BTCUSDT --order-id 12345

# 撤销某交易对全部挂单
binance-cli futures-usds cancel-all-open-orders --symbol BTCUSDT
```

## WebSocket 行情流 (futures-usds-streams)

### 公共频道(无需认证)

```bash
# K线流
binance-cli futures-usds-streams kline-candlestick-streams --symbol BTCUSDT --interval 1m

# 深度流(增量)
binance-cli futures-usds-streams diff-book-depth-streams --symbol BTCUSDT --update-speed 1000ms

# Mark Price + 资金费率流
binance-cli futures-usds-streams mark-price-stream --symbol BTCUSDT --update-speed 1000ms

# 全市场 Ticker
binance-cli futures-usds-streams all-market-tickers-streams
```

### 用户数据流(需 listen-key)

```bash
# 启动 listen-key
binance-cli futures-usds start-user-data-stream

# 使用 listen-key 订阅
binance-cli futures-usds-streams user-data --listen-key <KEY>
```

## Python 调用示例

```python
import asyncio
import json
from hermes_tools import terminal

async def call_binance_cli(command: str, **params) -> dict:
    """调用 binance-cli 并解析 JSON 输出"""
    args = [arg for k, v in params.items() for arg in (f"--{k.replace('_', '-')}", str(v))]
    full_cmd = f"binance-cli {command} {' '.join(args)}"
    result = await asyncio.to_thread(terminal, full_cmd)
    if result["exit_code"] != 0:
        raise RuntimeError(f"CLI failed: {result['output']}")
    return json.loads(result["output"])

# 使用
data = await call_binance_cli(
    "futures-usds ticker24hr-price-change-statistics",
    symbol="BTCUSDT"
)
print(f"BTC 价格: {data['lastPrice']}")
```

## 安全规则

> ⚠️ 来自 `references/auth.md`,**必须遵守**:

1. **永远不要** 运行 `printenv`、`env`、`export`(无具体变量名)
2. **永远不要** 用未锚定的 grep 搜索 env 文件(`^VARNAME=` 才允许)
3. **永远不要** echo 或 log 原始凭证
4. **永远不要** 泄露 key/secret 文件路径
5. **实盘交易前** 必须用户输入 `CONFIRM`

## 限流

- 公共接口: 6000 / 5min per IP
- 私有接口: 1200 / min per UID
- 超限返回 HTTP 429 → 用 retry/backoff 处理
