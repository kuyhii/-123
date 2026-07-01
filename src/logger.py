"""
src/logger.py - 基于 rich 的彩色日志
"""
import sys
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
from datetime import datetime
import logging

# 共享 console
_console = Console()


def get_logger(name: str, level: str = "INFO", log_to_file: bool = False) -> logging.Logger:
    """
    获取带 rich 美化的 logger

    用法:
        from src.logger import get_logger
        log = get_logger(__name__)
        log.info("hello")
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # 避免重复添加

    logger.setLevel(level.upper())
    logger.propagate = False

    # rich 控制台 handler
    rich_handler = RichHandler(
        console=_console,
        show_path=False,
        show_time=True,
        markup=True,
        rich_tracebacks=True,
    )
    rich_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(rich_handler)

    # 可选:文件 handler
    if log_to_file:
        try:
            from src.config import PROJECT_ROOT
            log_dir = PROJECT_ROOT / "logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / f"{datetime.now():%Y%m%d}.log"
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            logger.addHandler(file_handler)
        except Exception:
            # 文件日志失败不影响主流程
            pass

    return logger


# 快捷 logger
log = get_logger("quant-futures", log_to_file=True)


if __name__ == "__main__":
    log.info("🚀 logger 模块测试")
    log.warning("⚠️  warning 测试")
    log.error("❌ error 测试")
    log.debug("🔍 debug 测试")
