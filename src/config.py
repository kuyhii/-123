"""
src/config.py - 配置加载

从 .env 文件加载配置,封装为 dataclass,业务代码只依赖 Config,不直接读环境变量。
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 加载 .env(在项目根目录)
load_dotenv(PROJECT_ROOT / ".env")


def _getenv(key: str, default: str = "") -> str:
    """读取环境变量,trim 空白"""
    return os.getenv(key, default).strip()


def _getenv_float(key: str, default: float) -> float:
    try:
        return float(_getenv(key, str(default)))
    except ValueError:
        return default


def _getenv_int(key: str, default: int) -> int:
    try:
        return int(_getenv(key, str(default)))
    except ValueError:
        return default


@dataclass
class BinanceConfig:
    """Binance API 配置"""
    api_key: str = ""
    secret_key: str = ""
    env: str = "demo"               # prod | testnet | demo
    profile: str = "default"        # binance-cli profile 名


@dataclass
class TradingConfig:
    """交易参数"""
    default_symbol: str = "BTCUSDT"
    default_leverage: int = 10
    default_margin_type: str = "ISOLATED"   # ISOLATED | CROSSED


@dataclass
class RiskConfig:
    """风控参数"""
    max_position_size_pct: float = 30.0     # 单仓位占账户净值最大比例 %
    max_daily_loss_pct: float = 10.0        # 日内最大亏损熔断 %
    stop_loss_pct: float = 2.0              # 默认止损 %
    max_leverage: int = 20                  # 最大杠杆
    blacklist_symbols: list = field(default_factory=lambda: [])


@dataclass
class SystemConfig:
    """系统设置"""
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_to_file: bool = True


@dataclass
class Config:
    """全局配置"""
    binance: BinanceConfig = field(default_factory=BinanceConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    system: SystemConfig = field(default_factory=SystemConfig)

    @property
    def has_credentials(self) -> bool:
        """是否配置了 API key"""
        return bool(self.binance.api_key and self.binance.secret_key)

    def summary(self) -> str:
        return (
            f"环境: {self.binance.env}  |  "
            f"默认交易对: {self.trading.default_symbol}  |  "
            f"默认杠杆: {self.trading.default_leverage}x  |  "
            f"API Key: {'已配置' if self.has_credentials else '未配置'}"
        )


def load_config() -> Config:
    """加载配置"""
    return Config(
        binance=BinanceConfig(
            api_key=_getenv("BINANCE_API_KEY"),
            secret_key=_getenv("BINANCE_SECRET_KEY"),
            env=_getenv("BINANCE_API_ENV", "demo"),
            profile=_getenv("BINANCE_PROFILE", "default"),
        ),
        trading=TradingConfig(
            default_symbol=_getenv("DEFAULT_SYMBOL", "BTCUSDT"),
            default_leverage=_getenv_int("DEFAULT_LEVERAGE", 10),
            default_margin_type=_getenv("DEFAULT_MARGIN_TYPE", "ISOLATED"),
        ),
        risk=RiskConfig(
            max_position_size_pct=_getenv_float("MAX_POSITION_SIZE_PCT", 30.0),
            max_daily_loss_pct=_getenv_float("MAX_DAILY_LOSS_PCT", 10.0),
            stop_loss_pct=_getenv_float("STOP_LOSS_PCT", 2.0),
            max_leverage=_getenv_int("MAX_LEVERAGE", 20),
            blacklist_symbols=[
                s.strip() for s in _getenv("BLACKLIST_SYMBOLS", "").split(",") if s.strip()
            ],
        ),
        system=SystemConfig(
            log_level=_getenv("LOG_LEVEL", "INFO"),
            log_dir=_getenv("LOG_DIR", "./logs"),
            log_to_file=_getenv("LOG_TO_FILE", "true").lower() == "true",
        ),
    )


# 全局单例
CONFIG = load_config()


if __name__ == "__main__":
    # 单独跑:打印配置
    from src.logger import get_logger
    log = get_logger("config")
    cfg = CONFIG
    log.info("配置加载完成")
    log.info(cfg.summary())
    log.info(f"Binance env: {cfg.binance.env}")
    log.info(f"风险参数: {cfg.risk}")
