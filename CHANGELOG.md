# 更新日志 (CHANGELOG)

> 格式遵循 [Keep a Changelog](https://keepachangelog.com/)。
> 本仓库仅记录与**代码/产品**相关的变更;个人开发环境、迁移操作等不记录。

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

### 🔒 安全 (Security)
- 修复 `.gitignore` 锚定规则,避免误屏蔽源代码目录

---

## [0.1.0] - 2026-07-01

### ✨ 新增 (Added)
- 项目初始化与目录结构
- README.md、CHANGELOG.md、LICENSE
- 三份核心文档 (ARCHITECTURE、API_REFERENCE、STRATEGY_GUIDE)
- 全部源码首次推送

---

**关于历史 commit**: 早期 commit 中含有与本仓库无关的本地开发环境信息,已在后续 commit 中清理。
