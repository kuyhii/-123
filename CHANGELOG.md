# 更新日志 (CHANGELOG)

> 格式遵循 [Keep a Changelog](https://keepachangelog.com/)。
> 本仓库仅记录与**代码/产品**相关的变更;个人开发环境、迁移操作等不记录。

---

## [0.8.0] - 2026-07-01

### ✨ 新增 (Added)
- **执行器抽象层** `src/executor/`
  - `base.py`:`OrderExecutor` 抽象基类 + `ExecutionResult` 统一返回
  - `live_executor.py`:真实下单执行器(走 `binance-cli` 真实 API)
  - `paper_executor.py`:本地模拟执行器(内存账户,即时成交,持 PnL)
  - `order_router.py`:统一路由接口,根据 `EXECUTOR_MODE` 自动选执行器
- **真实盘 / 模拟盘切换**
  - `.env` 加 `EXECUTOR_MODE=paper|live`(默认 paper,最安全)
  - 同一套业务代码,只换执行器后端
  - **链路连贯性**:真实盘走币安,模拟盘用相同接口(下单/撤单/查余额/查持仓)本地跑
  - 真实盘用真数据模拟时,自动从 Binance 拉当前市价
- **真实盘安全保护**
  - 启动时校验:`BINANCE_API_ENV` 必须是 prod/testnet/demo
  - 启动时校验:必须配置 `BINANCE_API_KEY` / `BINANCE_SECRET_KEY`,缺一就拒启动
  - 每次下单前额外检查:
    - 账户净值 < $50 拒绝开仓
    - 单笔名义 > 账户 50% 拒绝(防止单笔爆仓)
  - 启动时发 `WARN` 通知(如果配了 Telegram)
  - 每次下单发 `WARN` + `TRADE` 通知
- **main.py 真实盘完整化**
  - 4 项确认清单(API key 权限 / EXECUTOR_MODE / 已在 demo 验证 / 资金承受力)
  - CONFIRM 二次确认
  - 强烈建议先 paper 跑 24-48 小时
  - OrderRouter 二次校验 is_real_money

### 🐛 修复 (Fixed)
- 修复 `order_router` `__init__` 没用保存 `kwargs`,paper 模式 `initial_balance` 失效
- 修复 `order_router.market` 不自动拉市价,paper 模拟盘没价格不能成交
- 修复 `paper_executor` 缺 `import sys` 导致 import 失败
- 修复 `base.py` 缺 `sys.path` 注入
- 修复 `live_executor` 启动日志被 `if not has_creds` 截断
- 修复 env 检查顺序:先验 `BINANCE_API_ENV` 再验 key

### 📊 验证结果
- pytest: **82 passed in 7.22s**
- paper_executor: 真实跑通(买→涨→卖有 PnL)
- live_executor: 启动安全检查通过(无 key 拒启动,无效 env 拒启动)
- order_router: 单例 + paper/live 自动分发
- main.py --help: 4 mode 含 live

---

## [0.7.0] - 2026-07-01

### ✨ 新增 (Added)
- **增强技术指标** `src/data/indicators.py`
  - MACD(金叉/死叉检测)
  - Bollinger Bands(%B 位置 + bandwidth 收窄检测)
  - ATR(平均真实波幅 + 趋势)
  - KDJ(随机指标 + 超买超卖)
  - OBV(能量潮)
  - 不依赖 pandas,纯 Python 实现
- **回测报告导出** `src/backtest/report.py`
  - HTML(打印友好 + 配色 + 卡片布局)
  - JSON(机器可读)
  - CSV(交易明细)
  - `save_report()` 一键保存
- **多币种回测** `src/backtest/multi_engine.py`
  - 从 trading_pairs.json 批量回测
  - asyncio 并发(可配 `max_concurrent` 限流)
  - 组合汇总报告(等权加权 PnL/胜率/夏普/回撤)
  - 各币种独立明细
- **Web 监控面板** `src/monitor/server.py`
  - 零依赖(仅用标准库 `http.server`)
  - 端点:`/`(HTML 仪表盘) / `/health` / `/signals` / `/trades` / `/orders` / `/api/summary`
  - 5 秒自动刷新
  - 显示系统状态、配置、组件健康、池子前 10
- **main.py 新命令**
  - `--multi-backtest`:多币种回测
  - `--top-n N`:回测池子前 N 币种
  - `--report`:回测后导出报告
  - `--monitor`:启动 Web 监控
  - `--monitor-port 8000`:自定义端口
- **测试** +17 个新测试,共 67 个
  - `test_indicators_v2.py`:MACD / Bollinger / ATR / KDJ / OBV

### 🐛 修复 (Fixed)
- 修复 `macd()` 浮点对齐问题(None 占位导致减法报错)
- 修复 `bollinger` %B 测试期望(价格上涨时 %B 必然 > 0.5)

### 📊 验证结果
- pytest: **67 passed in 5.43s**
- multi_engine: 导入正常
- monitor server: 真实启动,3 个端点 API 返回正确数据
- report: 生成 HTML/JSON/CSV 各一份(测试时)

---

## [0.6.0] - 2026-07-01

### ✨ 新增 (Added)
- **通知系统** `src/notify/notifier.py`
  - 多通道:控制台 + Telegram + 文件日志
  - 5 种严重级别:INFO / SIGNAL / TRADE / WARN / ERROR
  - 同事件 1 分钟内限流(防刷屏)
  - Telegram 配置: `.env` 加 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
- **断线重连** `src/utils/reconnect.py`
  - 装饰器模式:`@async_reconnecting_stream` 或 `@async_reconnecting_stream(max_attempts=5)`
  - 指数退避(1s → 2s → 4s → 8s,上限 60s)+ 抖动
  - 致命异常(fatal_exceptions)立即停止
  - async generator 资源自动关闭(`aclose`)
- **健康检查** `src/utils/health.py`
  - 单例 + 线程安全
  - 组件级状态:HEALTHY / DEGRADED / UNHEALTHY
  - 自动检测"长期无成功"为 stale
  - 整体健康判定 + 快照导出
- **Docker 部署** `Dockerfile` + `docker-compose.yml` + `.dockerignore`
  - Python 3.11 + Node 20 基础镜像
  - 一条 `docker compose up -d` 启动
  - 资源限制(1 CPU / 512MB)+ 日志轮转(10MB × 3)
  - 挂载 `data/` `logs/` `config/` 持久化
  - Dockerfile 含 `HEALTHCHECK` 指令
- **集成**:`paper_engine.py` 集成通知 + 健康检查
  - 启动 / 异常 / 中断时发通知
  - 每收到一根 K 线记录一次成功
- **测试套件** +15 个新测试,共 50 个
  - `test_health.py` 7 个场景
  - `test_notifier.py` 6 个场景
  - `test_reconnect.py` 4 个场景(含死循环回归测试)

### 🐛 修复 (Fixed)
- 修复 `async_reconnecting_stream` 装饰器签名(支持无参调用)
- 修复 `async for` 正常完成时死循环(用 `try` 内的 `else` 而非 `except StopAsyncIteration`)
- 修复 `reconnect.py` `factory=None` 时变 partial,允许无参调用
- 修复 3 个新模块缺 `sys.path` 注入(不能 `python xxx.py` 直接跑)
- 修复 `notifier.py` 顶部 docstring 重复导致 IndentationError

### 📊 验证结果
- pytest: **50 passed in 5.29s**
- notifier: 单独跑 + 集成到 paper_engine
- health: 3 组件状态正确显示
- reconnect: 4 个测试场景(断/正常/限重试/致命)
- docker-compose: YAML 语法正确

---

## [0.5.0] - 2026-07-01

### ✨ 新增 (Added)
- **测试套件** `tests/` — 33 个单元测试覆盖核心逻辑
  - `test_indicators.py`: SMA / EMA / RSI 测试
  - `test_risk.py`: 风控 6 个场景(正常/黑名单/超仓/熔断/平仓/回撤)
  - `test_position_sizer.py`: 仓位计算 5 个场景
  - `test_data_models.py`: 数据类解析测试
  - `test_strategy.py`: DualMA 4 个场景(基类/名/涨/跌)
  - pytest 8 / 9 兼容
- **持久化层** `src/storage/db.py` — SQLite 单文件
  - 5 张表:`klines` / `orders` / `signals` / `account_snapshots` / `trade_journal`
  - 4 个 Repository:`KlinesRepository` / `SignalsRepository` / `OrdersRepository` / `TradesRepository`
  - WAL 模式 + 索引优化
- **策略工厂** `src/strategy/factory.py`
  - `@register("name")` 装饰器注册
  - `create(name, **params)` 通过名称实例化
  - `available()` 列出所有注册策略
  - 延迟 import 解决循环依赖
- **多周期策略** `src/strategy/examples/multi_tf_trend.py` — `multi_tf_trend`
  - 双 EMA 趋势策略(3m 主 + 5m 长)
  - 框架共振 → 开仓,不一致 → 不开(过滤震荡)
- **模拟盘引擎** `src/engine/paper_engine.py`
  - 实时拉 K线 → 跑策略 → 风控 → 模拟成交 → 实时面板
  - rich 实时 dashboard(仓位/价格/PnL)
  - 所有交易持久化到 SQLite
  - `--paper-equity` / `--paper-duration` 可配
- **main.py 新命令**
  - `--list-strategies`: 列出所有策略
  - `--paper-equity 1000`: 模拟盘初始资金
  - `--paper-duration 60`: 模拟盘持续分钟
- **requirements.txt** 加 `pytest` + `pytest-asyncio`

### 🐛 修复 (Fixed)
- 修复 `dual_ma` 没注册到工厂(加了 `@register("dual_ma")` 装饰器)
- 修复 `factory.py` 与 `dual_ma.py` 循环导入(用 `importlib` 延迟导入)
- 修复 `paper_engine.py` 缺 `Signal` 导入

### 📊 验证结果
- pytest: **33 passed in 0.21s**
- 持久化: 5 表全可用,K线/订单/信号/成交 CRUD 正常
- 工厂: 2 个策略注册,`create/available` 工作
- 多周期策略: 双框架共振正确生成 BUY 信号
- DB 文件生成:`data/quant.db` (45 KB)

---

## [0.4.0] - 2026-07-01

### ✨ 新增 (Added)
- **交易对池调度系统** — 启动时拉取,每天定时更新,自动剔除不达标
  - `config/trading_pairs.json`: 运行时生成(40 币种 + 24h 交易量快照)
  - `src/strategy/trading_pairs.py`: load / refresh / in_pairs / get_diff_report
  - `src/scheduler/pair_updater.py`: 每天 00:00 UTC(北京 8:00)自动刷新
  - 排除 `underlyingSubType=TradFi` 的股票/实物贵金属/原油合约
  - 池子大小可通过 `TRADING_PAIRS_TOP_N` 配置(默认 40)
  - 启动行为可通过 `PAIR_AUTO_UPDATE_ON_START` 控制
- **main.py 新命令**
  - `--refresh-pairs` / `--update-now`: 立即刷新池子
  - `--scheduler`: 启动后台调度器(常驻进程,每天定时)
- **Config 升级** `src/config.py`
  - `CoinPoolConfig` 改名实质: `top_n=40` / `update_time_utc="00:00"` / `auto_update_on_start=True`

### 📝 重命名 (Renamed)
- `config/coin_pool.json` → `config/trading_pairs.json`(更准确)
- `src/strategy/coin_pool.py` → `src/strategy/trading_pairs.py`
- 参数 `COIN_POOL_FILE` → `TRADING_PAIRS_FILE`

### 📊 实测结果(本次启动)
- 拉到 529 个 USDT 加密币永续
- 过滤后取前 40:BTC 13.5B → RAVE 65.6M USDT 24h 量
- 排除了 XAUUSDT / XAGUSDT / SOXLUSDT / MSTRUSDT 等 TradFi

### 🕐 调度行为
- 下次执行时间 = 00:00 UTC(用户配置,可改)
- 计算函数: `_seconds_until_next(0, 0)` → 当前 07:04 UTC 时返回 16.92 小时

---

## [0.3.0] - 2026-07-01

### ✨ 新增 (Added)
- **交易品种池** `config/coin_pool.json` + `src/strategy/coin_pool.py`
  - 默认按 USDT 永续 24h 交易量排序取前 30
  - 排除 `underlyingSubType=TradFi` 的股票/贵金属/原油合约
  - `--refresh-pool` 命令从币安拉最新池
  - 单文件入口:`python src/strategy/coin_pool.py --show` / `--refresh`
- **仓位大小计算** `src/executor/position_sizer.py`
  - 公式:每单保证金 = 账户净值 × 4%;名义 = 保证金 × 杠杆
  - 单独可跑 `python src/executor/position_sizer.py` 看 4 种场景
- **配置系统升级** `src/config.py`
  - 新增 `TradingConfig`: `leverage=20` / `kline_intervals=[3m,5m]` / `order_pct_of_margin=4.0`
  - 新增 `CoinPoolConfig`: 池文件路径
  - 新增 `kline_intervals` 多周期支持(策略可同时用 3m + 5m)
- **.env.example** 更新参数注释
- **main.py** 加 `--refresh-pool` 命令 + `--interval` 默认从 config 读

### 📊 默认策略参数(v0.3.0 起)
- 杠杆:**20x**(全策略统一)
- K线周期:**3m + 5m**(多时间框架)
- 交易品种:**USDT 永续 24h 交易量前 30**(已过滤 TradFi)
- 下单金额:**账户净值 × 4% 保证金**

### 📈 实测仓位计算(用户给 100 USDT 账户)
- BTC $58,000 → 0.00138 BTC (4 USDT 保证金, 80 USDT 名义)
- ETH $1,500 → 0.533 ETH
- SOL $74 → 108 SOL

---

## [0.2.1] - 2026-07-01

### 🐛 修复 (Fixed)
- `requirements.txt` 移除顶部 docstring(`uv pip` 严格解析会失败)
- `src/adapter/binance_cli.py` 顶部加入 `sys.path` 注入,支持 `python src/<module>.py` 直接运行
- `src/backtest/engine.py` 修复 `_fetch_history` 里 `limit` 关键字参数重复问题
- `src/main.py` 修复回测输出 `print(result.summary)` 未调用方法

### ✅ 验证 (Verified)
- 装好真实环境(`node 24` + `binance-cli 1.3.0` + Python `rich`/`dotenv`)
- demo.py 真实跑通(BTC 当前价 $58,605)
- 回测真实跑通(7 天 BTC,1500 根 K 线,97 次交易)

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
