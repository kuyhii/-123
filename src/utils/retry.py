"""
src/utils/retry.py - 重试装饰器

支持异步和同步两种,指数退避,可配置重试异常类型。
"""
import asyncio
import functools
import time
from typing import Tuple, Type, Optional

from src.logger import get_logger

log = get_logger("retry")


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Optional[callable] = None,
):
    """异步重试装饰器"""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        log.error(f"❌ 重试 {max_attempts} 次后仍失败: {fn.__name__} - {e}")
                        raise
                    log.warning(
                        f"⚠️  {fn.__name__} 第 {attempt}/{max_attempts} 次失败: {e},"
                        f" {current_delay:.1f}s 后重试"
                    )
                    if on_retry:
                        on_retry(attempt, e)
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            raise last_exc
        return wrapper
    return decorator


def sync_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Optional[callable] = None,
):
    """同步重试装饰器"""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        log.error(f"❌ 重试 {max_attempts} 次后仍失败: {fn.__name__} - {e}")
                        raise
                    log.warning(
                        f"⚠️  {fn.__name__} 第 {attempt}/{max_attempts} 次失败: {e},"
                        f" {current_delay:.1f}s 后重试"
                    )
                    if on_retry:
                        on_retry(attempt, e)
                    time.sleep(current_delay)
                    current_delay *= backoff
            raise last_exc
        return wrapper
    return decorator
