"""
tests/test_reconnect.py - 断线重连测试
"""
import pytest
import asyncio
from src.utils.reconnect import async_reconnecting_stream


@pytest.mark.asyncio
async def test_reconnects_on_error():
    """流断开时自动重连"""
    counter = [0]

    async def flaky():
        counter[0] += 1
        if counter[0] == 1:
            yield "a"
            raise ConnectionError("模拟断开")
        elif counter[0] == 2:
            yield "b"
            yield "c"
            return  # 正常结束
        else:
            return

    @async_reconnecting_stream
    async def stream():
        async for x in flaky():
            yield x

    items = []
    async for x in stream():
        items.append(x)
        if len(items) >= 3:
            break

    assert "a" in items
    assert "b" in items
    assert "c" in items
    assert counter[0] >= 2  # 至少调用了 2 次


@pytest.mark.asyncio
async def test_normal_completion():
    """正常完成时不重连"""
    counter = [0]

    async def one_shot():
        counter[0] += 1
        yield "x"
        yield "y"
        return

    @async_reconnecting_stream
    async def stream():
        async for x in one_shot():
            yield x

    items = []
    async for x in stream():
        items.append(x)

    assert items == ["x", "y"]
    assert counter[0] == 1


@pytest.mark.asyncio
async def test_max_attempts():
    """达到 max_attempts 后停止"""
    import time
    counter = [0]

    async def always_fail():
        counter[0] += 1
        raise ConnectionError(f"fail {counter[0]}")

    from src.utils.reconnect import async_reconnecting_stream

    @async_reconnecting_stream(max_attempts=2)
    async def stream():
        async for x in always_fail():
            yield x

    items = []
    start = time.time()
    async for x in stream():
        items.append(x)
        if time.time() - start > 5:
            break

    # 试了 2 次后停止
    assert counter[0] <= 2
    assert items == []


@pytest.mark.asyncio
async def test_fatal_exception_stops():
    """致命异常立即停止"""
    counter = [0]

    async def fatal_error():
        # 必须是 async generator(有 yield),async for 才认
        counter[0] += 1
        yield "never"  # 实际不会 yield
        raise ValueError("fatal")

    from src.utils.reconnect import async_reconnecting_stream

    @async_reconnecting_stream(fatal_exceptions=(ValueError,))
    async def stream_fatal():
        async for x in fatal_error():
            yield x

    items = []
    async for x in stream_fatal():
        items.append(x)
    # 致命错误:yield 一次后抛 fatal,被 fatal_exceptions 拦截,只跑 1 次
    assert items == ["never"]
    assert counter[0] == 1
