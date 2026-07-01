# 更新日志 (CHANGELOG)

---

## [0.2.0] - 2026-07-01

### ✨ 新增 (Added)
- **L0 适配层** `src/adapter/` — `binance_cli.py` 异步/同步封装、`errors.py` 异常体系
- **L1 数据层** `src/data/` — `market_data.py` (REST)、`ws_kline.py` / `ws_user_data.py` (WS)、`models.py` 数据类
- **L2 账户层** `src/account/` — 余额/持仓/订单查询、缓存、便捷访问
- **L3 执行层** `src/executor/order_router.py` — 市价/限价/止损/止盈/全撤
- **L4 风控层** `src/risk/risk_manager.py` — 信号检查、仓位限制、日内熔断
- **L5 策略层** `src/strategy/` — 策略基类 + 双均线示例
- **回测引擎** `src/backtest/engine.py` — 历史 K 线 + 性能统计
- **配置系统** `src/config.py` — .env → dataclass
- **彩色日志** `src/logger.py` — rich-based
- **重试工具** `src/utils/retry.py` — 异步+同步
- **手写技术指标** `sma`、`ema`、`rsi`(不依赖 pandas)
- **每模块可独立运行测试**(`python src/<module>.py`)

### 📝 文档 (Documentation)
- README 重写:模块化说明、本地启动、单模块测试
- 每个模块顶部有 docstring + Examples
- Demo 模式展示完整功能

### 🔄 变更 (Changed)
- requirements.txt 精简到 2 个核心包(`rich` + `python-dotenv`)
- `config/` 改为普通目录(不是包了)
- `main.py` 完整重写,支持 4 种模式

### ⚠️ 已知限制
- `binance-cli` 未装时只能验证语法
- WS 模块依赖子进程,Windows 下需要 Node.js ≥ 18
- 模拟盘 / 实盘只完成下单部分,策略联动待补

---

## [0.1.1] - 2026-07-01

### 🔄 变更 (Changed)
- 项目目录从 `C:\Users\Administrator\quant-futures` 迁移至 `D:\quant-futures`
- Git 远程仓库不变 (`git@github.com:kuyhii/-123.git`)

---

## [0.1.0] - 2026-07-01

### ✨ 新增 (Added)
- 项目初始化与目录结构
- README.md、CHANGELOG.md、LICENSE
- 三份核心文档 (ARCHITECTURE、API_REFERENCE、STRATEGY_GUIDE)
- 25 个项目文件推送至 GitHub
