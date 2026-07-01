# 量化合约交易系统 (Quantitative Futures Trading System)

基于 **Binance USDT 永续合约 (USDS-M Futures)** 的模块化量化交易系统。

集成官方 [binance-skills-hub](https://github.com/binance/binance-skills-hub) 的 `binance-cli` 工具,
Python 端封装每个能力为独立模块,支持本地运行、回测、模拟盘、实盘。

---

## ✨ 特性

- 🧩 **完全模块化** — L0~L5 每层独立,可单独运行测试
- 📊 **实时行情** — K线 / 深度 / Ticker / Mark Price / Funding Rate
- 💼 **账户管理** — 余额 / 持仓 / 杠杆 / 保证金模式
- 🎯 **策略引擎** — 插拔式接口,自定义策略只需继承 `Strategy`
- 🛡️ **风控体系** — 仓位 / 止损 / 日内熔断 / 黑名单
- 🚀 **执行层** — 限价 / 市价 / 算法单 (TP/SL) / 批量下单
- 📈 **回测框架** — 历史 K 线回放 + 性能指标
- 🎨 **彩色日志** — 基于 rich,运行时清晰直观

---

## 🏗️ 架构(L0 ~ L5)

```
┌─────────────────────────────────────────────────────────┐
│  L5  Strategy        策略层 (信号生成)                   │
├─────────────────────────────────────────────────────────┤
│  L4  Risk            风控层 (仓位/熔断/止损)            │
├─────────────────────────────────────────────────────────┤
│  L3  Executor        执行层 (下单/撤单)                 │
├─────────────────────────────────────────────────────────┤
│  L2  Account         账户层 (余额/持仓/订单)            │
├─────────────────────────────────────────────────────────┤
│  L1  Data            数据层 (REST + WebSocket)           │
├─────────────────────────────────────────────────────────┤
│  L0  Adapter         适配层 (binance-cli 封装)          │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 本地启动

### 1. 安装依赖

```bash
# Python 依赖(只用 2 个核心包,简单)
pip install -r requirements.txt

# Node.js CLI 工具(必需,用于调用 Binance API)
npm install -g @binance/binance-cli
```

### 2. 配置环境变量

```bash
# Windows
copy .env.example .env
# macOS/Linux
cp .env.example .env
```

编辑 `.env`,填入您的 Binance API Key / Secret。

> **没有 API key 也行!** 公开行情接口(查价格、K线)不需要认证,只有下单、查账户才需要。
> 建议先在 Binance 创建 **demo trading** 的 API key(`BINANCE_API_ENV=demo`)。

### 3. 创建 CLI Profile

```bash
binance-cli profile create --name default --api-key <KEY> --api-secret <SECRET> --env demo
```

### 4. 跑起来

```bash
# Demo 模式:验证环境 + 拉行情
python src/main.py --mode demo

# 回测:在历史数据上跑策略
python src/main.py --mode backtest --days 90

# 模拟盘:实时行情跑策略,但不下单
python src/main.py --mode paper

# 实盘:真下单(危险!)
python src/main.py --mode live
# 会要求输入 CONFIRM
```

### 5. 单模块测试

每个模块都能独立跑,验证某层功能:

```bash
# 单独测 L0 适配层
python src/adapter/binance_cli.py

# 单独测 L1 数据层
python src/data/market_data.py

# 单独测 L1 WS 模块
python src/data/ws_kline.py

# 单独测 L2 账户
python src/account/account.py

# 单独测 L3 执行
python src/executor/order_router.py

# 单独测 L4 风控
python src/risk/risk_manager.py
```

---

## 📁 目录结构

```
quant-futures/
├── README.md                  # 本文件
├── CHANGELOG.md
├── LICENSE
├── package.json               # binance-cli 依赖
├── requirements.txt           # Python 依赖(精简:rich + dotenv)
├── .env.example               # 环境变量模板
├── .gitignore
│
├── src/                       # 所有源码
│   ├── main.py                # 主入口
│   ├── demo.py                # demo 模式
│   ├── config.py              # 配置加载(.env → dataclass)
│   ├── logger.py              # rich 彩色日志
│   │
│   ├── adapter/               # L0
│   │   ├── binance_cli.py     # binance-cli 封装
│   │   └── errors.py          # 异常体系
│   │
│   ├── data/                  # L1
│   │   ├── models.py          # 数据类
│   │   ├── market_data.py     # 公开行情(REST)
│   │   ├── ws_kline.py        # K线 WS
│   │   └── ws_user_data.py    # 用户数据 WS
│   │
│   ├── account/               # L2
│   │   ├── models.py
│   │   └── account.py
│   │
│   ├── executor/              # L3
│   │   └── order_router.py
│   │
│   ├── risk/                  # L4
│   │   └── risk_manager.py
│   │
│   ├── strategy/              # L5
│   │   ├── base.py            # Strategy 基类
│   │   ├── signal.py          # Signal 数据类
│   │   └── examples/
│   │       └── dual_ma.py     # 双均线示例
│   │
│   ├── backtest/              # 回测
│   │   └── engine.py
│   │
│   └── utils/
│       └── retry.py           # 重试装饰器
│
├── tests/                     # 测试(逐步补充)
├── docs/                      # 详细文档
├── config/                    # 配置文件目录
├── data/                      # 数据存储
└── logs/                      # 日志输出
```

---

## ⚠️ 安全提示

- **永远不要** 把 `.env` 提交到仓库(已 .gitignore)
- **永远不要** 开启 API key 的**提现权限**
- **实盘前** 必须输入 `CONFIRM` 确认
- **先 demo / testnet,再小资金,再大资金**

---

## 📚 详细文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 架构详解
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) — binance-cli 命令速查
- [docs/STRATEGY_GUIDE.md](docs/STRATEGY_GUIDE.md) — 如何写自己的策略

---

## 📝 更新日志

见 [CHANGELOG.md](CHANGELOG.md)

---

**License**: MIT | **Author**: kuyhii
