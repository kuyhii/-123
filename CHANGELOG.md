# 更新日志 (CHANGELOG)

所有重要变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.1.0] - 2026-07-01

### ✨ 新增 (Added)
- 项目初始化与目录结构
- README.md 项目说明
- .gitignore 配置文件
- requirements.txt Python 依赖
- package.json Node.js 依赖 (binance-cli)
- .env.example 环境变量示例
- LICENSE MIT 许可证
- LICENSE 中加入风险免责声明
- docs/ 目录及三个核心文档:
  - ARCHITECTURE.md 架构详解
  - API_REFERENCE.md binance-cli API 速查
  - STRATEGY_GUIDE.md 策略开发指南
- src/ 目录及分层模块占位
- data/.gitkeep
- logs/.gitkeep

### 📝 文档 (Documentation)
- 项目架构图 (L0~L5 分层)
- binance-cli 集成方案
- 快速开始指南
- 安全提示

### ⚠️ 重要提示
- 强烈建议在 demo/testnet 环境起步
- 实盘交易前必须人工 CONFIRM 确认
- API key 不得提交到仓库

---

## 路线图 (Roadmap)

### [0.2.0] - 下一步
- [ ] L0 适配层:`adapter/binance_cli.py`
- [ ] L1 数据层:WS 行情接入
- [ ] 第一个 demo:查询 BTCUSDT 行情

### [0.3.0]
- [ ] L2 账户层
- [ ] L3 执行层(下单/撤单)
- [ ] L4 风控层
- [ ] L5 第一个示例策略

### [0.4.0]
- [ ] 回测框架
- [ ] 历史数据下载
- [ ] 策略性能报告

### [0.5.0]
- [ ] 模拟盘模拟运行
- [ ] 监控告警
- [ ] Web 控制台(可选)

### [1.0.0]
- [ ] 实盘生产部署
- [ ] 完整文档
- [ ] 测试覆盖
