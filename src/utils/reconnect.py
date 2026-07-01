"""
src/utils/reconnect.py - 断线重连装饰器

为异步生成器(WS 流)提供自动重连:
- 指数退避(1s → 2s → 4s → 8s,上限 60s)
- 记录重连次数
- 致命错误(认证)立即停
"""
import sys
import asyncio
import random
from functools import partial, wraps
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

# 让 `python src/utils/reconnect.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.logger import get_logger

log = get_logger("reconnect")


def async_reconnecting_stream(
    factory=None,
    max_attempts: int = -1,         # -1 = 永远重试
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff: float = 2.0,
    fatal_exceptions: tuple = (),
):
    """
    装饰器:把异步生成器工厂变成自动重连版本

    Args:
        factory: 异步生成器工厂(无参,返回 AsyncIterator)
                 如果为 None,返回 partial 装饰器
        max_attempts: 最大重试次数,-1 = 无限
        initial_delay: 首次重试延迟(秒)
        max_delay: 最大延迟(秒)
        backoff: 退避系数
        fatal_exceptions: 这些异常触发后立即停止,不重试

    用法:
        @async_reconnecting_stream
        async def my_stream():
            async for msg in ws.recv():
                yield msg

        @async_reconnecting_stream(max_attempts=5, fatal_exceptions=(AuthError,))
        async def my_stream():
            async for msg in ws.recv():
                yield msg

        async for msg in my_stream():
            process(msg)
    """
    if factory is None:
        # 无参调用,返回真正的装饰器
        from functools import partial
        return partial(
            async_reconnecting_stream,
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            backoff=backoff,
            fatal_exceptions=fatal_exceptions,
        )

    async def wrapped():
        attempt = 0
        delay = initial_delay
        while True:
            gen = factory()
            try:
                async for item in gen:
                    attempt = 0  # 成功后重置
                    delay = initial_delay
                    yield item
                # async for 正常完成(generator return)
                log.info("流正常结束")
                return
            except fatal_exceptions as e:
                log.error(f"致命错误,不再重试: {e}")
                return
            except Exception as e:
                attempt += 1
                if max_attempts > 0 and attempt > max_attempts:
                    log.error(f"已达最大重试次数 {max_attempts},停止")
                    return
                # 抖动避免雪崩
                jitter = random.uniform(0, 0.5)
                sleep = min(delay + jitter, max_delay)
                log.warning(
                    f"流断开(第 {attempt} 次): {type(e).__name__}: {e} "
                    f"→ {sleep:.1f}s 后重试"
                )
                await gen.aclose()  # 关闭旧 generator,避免资源泄漏
                await asyncio.sleep(sleep)
                delay = min(delay * backoff, max_delay)
    return wrapped


# ==================== 单独测试 ====================
if __name__ == "__main__":
    print("🔌 断线重连测试\n")

    # 模拟一个 3 次后停止的流
    counter = [0]

    async def flaky_factory():
        counter[0] += 1
        n = counter[0]
        if n == 1:
            yield "msg-1"
            raise ConnectionError("模拟断开 1")
        elif n == 2:
            yield "msg-2"
            yield "msg-3"
            raise ConnectionError("模拟断开 2")
        elif n == 3:
            yield "msg-4"
            # 这次正常结束
        else:
            return

    import time
    start = time.time()

    @async_reconnecting_stream
    async def stream():
        gen = flaky_factory()
        async for x in gen:
            yield x

    async def test():
        items = []
        async for x in stream():
            items.append(x)
            if len(items) >= 4:
                break
        return items

    items = asyncio.run(test())
    print(f"\n收到 {len(items)} 条: {items}")
    print(f"实际重连 {counter[0] - 1} 次,耗时 {time.time() - start:.1f}s")
