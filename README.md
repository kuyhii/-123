# 量化合约交易系统 (Quantitative Futures Trading System)

基于 **Binance USDT 永续合约 (USDS-M Futures)** 的量化交易系统,集成官方 [binance-skills-hub](https://github.com/binance/binance-skills-hub) 提供的 `binance-cli` 工具。

---

## ✨ 功能特性

- 📊 **实时行情**: K线 / 深度 / Ticker / Mark Price / Funding Rate (WebSocket)
- 💼 **账户管理**: 余额 / 持仓 / 杠杆 / 保证金模式
- 🎯 **策略引擎**: 插拔式策略接口,支持趋势 / 网格 / 套利等多种策略
- 🛡️ **风控体系**: 仓位上限 / 单笔止损 / 日内熔断 / 黑名单
- 🚀 **执行层**: 限价 / 市价 / 算法单 (TP/SL) / 批量下单
- 📈 **回测框架**: 基于历史 K 线的策略回测
- 📝 **完整日志**: 订单、成交、信号、资金变动全记录

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  L5  策略层 (Strategies)        - 信号生成               │
├─────────────────────────────────────────────────────────┤
│  L4  风控层 (Risk Manager)      - 仓位 / 熔断 / 止损     │
├─────────────────────────────────────────────────────────┤
│  L3  执行层 (Executor)          - 订单路由 / 下单        │
├─────────────────────────────────────────────────────────┤
│  L2  账户层 (Account)           - 余额 / 持仓 / 订单状态│
├─────────────────────────────────────────────────────────┤
│  L1  数据层 (Data)              - WS 行情 / 历史 K 线   │
├─────────────────────────────────────────────────────────┤
│  L0  binance-cli 适配层 (Adapter) - CLI 封装 / 重试     │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
quant-futures/
├── README.md                  # 本文件
├── requirements.txt           # Python 依赖
├── package.json               # Node.js 依赖 (binance-cli)
├── .env.example               # 环境变量示例
├── .gitignore
├── docs/                      # 文档
│   ├── ARCHITECTURE.md        # 架构详细说明
│   ├── API_REFERENCE.md       # binance-cli API 速查
│   └── STRATEGY_GUIDE.md      # 策略开发指南
├── src/                       # 源代码
│   ├── adapter/               # L0: binance-cli 适配层
│   ├── data/                  # L1: 数据层
│   ├── account/               # L2: 账户层
│   ├── executor/              # L3: 执行层
│   ├── risk/                  # L4: 风控层
│   ├── strategy/              # L5: 策略层
│   ├── backtest/              # 回测框架
│   ├── utils/                 # 工具
│   └── main.py                # 主入口
├── tests/                     # 测试
├── config/                    # 配置文件
│   ├── settings.yaml
│   └── profiles/              # API profile 配置
├── logs/                      # 日志
└── data/                      # 数据存储
```

---

## 🚀 快速开始

### 1. 安装 binance-cli (Node.js)

```bash
npm install -g @binance/binance-cli
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`,填入您的 API Key / Secret。

### 4. 创建 CLI profile

```bash
binance-cli profile create --name default --api-key <KEY> --api-secret <SECRET> --env testnet
```

### 5. 运行 demo

```bash
python src/main.py --symbol BTCUSDT --mode demo
```

---

## ⚠️ 重要安全提示

- **实盘交易前必须用户输入 `CONFIRM` 确认**
- 永远不要把 `.env` 或 `*.key` 文件提交到仓库
- 默认在 **testnet / demo** 环境运行
- 建议先用 `binance-cli futures-usds test-order` 测试下单

---

## 📚 参考资料

- [Binance Skills Hub](https://github.com/binance/binance-skills-hub)
- [binance-cli NPM](https://www.npmjs.com/package/@binance/binance-cli)
- [Binance Futures API 文档](https://developers.binance.com/docs/derivatives/usds-margined-futures)

---

## 📝 更新日志

### v0.1.0 (2026-07-01)
- 项目初始化
- 完整目录结构
- 文档体系建立

---

**License**: MIT
**Author**: kuyhii
