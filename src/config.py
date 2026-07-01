"""
src/config.py - 配置加载

从 .env 文件加载配置,封装为 dataclass,业务代码只依赖 Config,不直接读环境变量。
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

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


def _getenv_list(key: str, default: str = "") -> list:
    """逗号分隔 → list"""
    val = _getenv(key, default)
    if not val:
        return []
    return [s.strip() for s in val.split(",") if s.strip()]


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
    leverage: int = 20              # 全策略统一杠杆
    margin_type: str = "ISOLATED"
    kline_intervals: list = field(default_factory=lambda: ["3m", "5m"])
    order_pct_of_margin: float = 4.0  # 每单保证金占账户净值 %

    @property
    def has_multi_timeframe(self) -> bool:
        return len(self.kline_intervals) > 1


@dataclass
class RiskConfig:
    """风控参数"""
    max_position_size_pct: float = 4.0       # 单币种最大持仓保证金占账户净值
    max_daily_loss_pct: float = 10.0
    stop_loss_pct: float = 2.0
    max_leverage: int = 20
    blacklist_symbols: list = field(default_factory=list)


@dataclass
class CoinPoolConfig:
    """交易品种池"""
    file: str = "config/trading_pairs.json"
    top_n: int = 40                              # 池子大小
    update_time_utc: str = "00:00"               # 每天更新时刻(UTC)
    auto_update_on_start: bool = True            # 启动时是否自动刷新

    def get_path(self) -> Path:
        return PROJECT_ROOT / self.file

    def load_symbols(self) -> list:
        """从 json 加载币种列表"""
        import json
        path = self.get_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("symbols", [])
        except Exception:
            return []


@dataclass
class SystemConfig:
    """系统设置"""
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_to_file: bool = True
    executor_mode: str = "paper"            # paper | live(默认 paper,最安全)


@dataclass
class Config:
    """全局配置"""
    binance: BinanceConfig = field(default_factory=BinanceConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    pool: CoinPoolConfig = field(default_factory=CoinPoolConfig)
    system: SystemConfig = field(default_factory=SystemConfig)

    @property
    def has_credentials(self) -> bool:
        return bool(self.binance.api_key and self.binance.secret_key)

    def summary(self) -> str:
        return (
            f"环境: {self.binance.env}  |  "
            f"杠杆: {self.trading.leverage}x  |  "
            f"每单保证金: {self.trading.order_pct_of_margin}%  |  "
            f"K线: {','.join(self.trading.kline_intervals)}  |  "
            f"币种池: {len(self.pool.load_symbols())} 个  |  "
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
            leverage=_getenv_int("LEVERAGE", 20),
            margin_type=_getenv("DEFAULT_MARGIN_TYPE", "ISOLATED"),
            kline_intervals=_getenv_list("KLINE_INTERVALS", "3m,5m") or ["3m", "5m"],
            order_pct_of_margin=_getenv_float("ORDER_PCT_OF_MARGIN", 4.0),
        ),
        risk=RiskConfig(
            max_position_size_pct=_getenv_float("MAX_POSITION_SIZE_PCT", 4.0),
            max_daily_loss_pct=_getenv_float("MAX_DAILY_LOSS_PCT", 10.0),
            stop_loss_pct=_getenv_float("STOP_LOSS_PCT", 2.0),
            max_leverage=_getenv_int("MAX_LEVERAGE", 20),
            blacklist_symbols=[
                s.strip() for s in _getenv("BLACKLIST_SYMBOLS", "").split(",") if s.strip()
            ],
        ),
        pool=CoinPoolConfig(
            file=_getenv("TRADING_PAIRS_FILE", "config/trading_pairs.json"),
            top_n=_getenv_int("TRADING_PAIRS_TOP_N", 40),
            update_time_utc=_getenv("PAIR_UPDATE_TIME_UTC", "00:00"),
            auto_update_on_start=_getenv("PAIR_AUTO_UPDATE_ON_START", "true").lower() == "true",
        ),
        system=SystemConfig(
            log_level=_getenv("LOG_LEVEL", "INFO"),
            log_dir=_getenv("LOG_DIR", "./logs"),
            log_to_file=_getenv("LOG_TO_FILE", "true").lower() == "true",
            executor_mode=_getenv("EXECUTOR_MODE", "paper").lower(),
        ),
    )


# 全局单例
CONFIG = load_config()


if __name__ == "__main__":
    from src.logger import get_logger
    log = get_logger("config")
    cfg = CONFIG
    log.info("配置加载完成")
    log.info(cfg.summary())
    log.info(f"币种池前 5: {cfg.pool.load_symbols()[:5]}")
