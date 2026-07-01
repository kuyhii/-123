"""
src/adapter/binance_cli.py - L0 适配层

封装 `binance-cli` 子进程调用,提供:
- 异步调用:async def call(...)
- 同步调用:def call_sync(...)
- 错误分类、自动重试
"""
import asyncio
import json
import subprocess
import shutil
from typing import Any, Optional
from pathlib import Path

from src.adapter.errors import (
    BinanceCLIError, classify_error, BinanceRateLimitError, BinanceNetworkError,
)
from src.utils.retry import async_retry, sync_retry
from src.logger import get_logger

log = get_logger("adapter")

# binance-cli 路径(支持 Windows / Linux)
BINANCE_CLI = shutil.which("binance-cli") or "binance-cli"


def _is_installed() -> bool:
    """检测 binance-cli 是否安装"""
    return shutil.which("binance-cli") is not None


async def call(
    module: str,
    command: str,
    profile: Optional[str] = None,
    parse_json: bool = True,
    timeout: float = 30.0,
    **params,
) -> Any:
    """
    异步调用 binance-cli

    Args:
        module:    binance-cli 子模块,例如 "futures-usds"、"futures-usds-streams"
        command:   命令名,例如 "kline-candlestick-data"
        profile:   profile 名(可选,默认使用 active profile)
        parse_json:是否把 stdout 解析为 JSON
        timeout:   超时秒数
        **params:  CLI 参数,会转换为 --key value 形式

    Returns:
        解析后的 dict/list 或原始字符串

    Raises:
        BinanceCLIError: 调用失败
        FileNotFoundError: binance-cli 未安装

    Examples:
        >>> data = await call("futures-usds", "ticker24hr-price-change-statistics", symbol="BTCUSDT")
        >>> print(data["lastPrice"])
    """
    if not _is_installed():
        raise FileNotFoundError(
            "binance-cli 未安装。请先运行: npm install -g @binance/binance-cli"
        )

    args = _build_args(module, command, profile, params)
    cmd_str = " ".join(args)

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceRateLimitError, BinanceNetworkError),
    )
    async def _run():
        log.debug(f"exec: {cmd_str}")
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise BinanceNetworkError(f"命令超时 ({timeout}s): {cmd_str}")

        stdout_s = stdout.decode("utf-8", errors="replace").strip()
        stderr_s = stderr.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            err = classify_error(stderr_s, proc.returncode)
            err.stderr = stderr_s
            raise err

        if parse_json and stdout_s:
            try:
                return json.loads(stdout_s)
            except json.JSONDecodeError as e:
                log.warning(f"JSON 解析失败,返回原文: {e}")
                return stdout_s
        return stdout_s

    return await _run()


def call_sync(
    module: str,
    command: str,
    profile: Optional[str] = None,
    parse_json: bool = True,
    timeout: float = 30.0,
    **params,
) -> Any:
    """
    同步版本(在不能 async 的场景使用,如主入口分发)

    用法同 call(),阻塞执行。
    """
    if not _is_installed():
        raise FileNotFoundError(
            "binance-cli 未安装。请先运行: npm install -g @binance/binance-cli"
        )

    args = _build_args(module, command, profile, params)

    @sync_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceRateLimitError,),
    )
    def _run():
        log.debug(f"exec (sync): {' '.join(args)}")
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, encoding="utf-8"
        )
        if result.returncode != 0:
            err = classify_error(result.stderr, result.returncode)
            err.stderr = result.stderr
            raise err
        out = result.stdout.strip()
        if parse_json and out:
            try:
                return json.loads(out)
            except json.JSONDecodeError:
                return out
        return out

    return _run()


def _build_args(module: str, command: str, profile: Optional[str], params: dict) -> list:
    """构造 CLI 参数列表"""
    args = [BINANCE_CLI, module, command]
    if profile:
        args.extend(["--profile", profile])
    for k, v in params.items():
        if v is None:
            continue
        # key 转 kebab-case
        key = k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                args.append(f"--{key}")
        elif isinstance(v, (list, tuple)):
            for item in v:
                args.extend([f"--{key}", str(item)])
        else:
            args.extend([f"--{key}", str(v)])
    return args


# ==================== 便捷封装(按子模块) ====================

class FuturesUSDS:
    """USDT 永续合约 (futures-usds) 命令封装"""
    module = "futures-usds"

    @staticmethod
    async def ticker_24h(symbol: str, **kw) -> dict:
        return await call("futures-usds", "ticker24hr-price-change-statistics",
                          symbol=symbol, **kw)

    @staticmethod
    async def kline(symbol: str, interval: str, limit: int = 100, **kw) -> list:
        return await call("futures-usds", "kline-candlestick-data",
                          symbol=symbol, interval=interval, limit=limit, **kw)

    @staticmethod
    async def orderbook(symbol: str, limit: int = 20, **kw) -> dict:
        return await call("futures-usds", "order-book", symbol=symbol, limit=limit, **kw)

    @staticmethod
    async def mark_price(symbol: Optional[str] = None, **kw) -> Any:
        params = {} if not symbol else {"symbol": symbol}
        return await call("futures-usds", "mark-price", **params, **kw)

    @staticmethod
    async def funding_rate(symbol: Optional[str] = None, limit: int = 10, **kw) -> Any:
        params = {} if not symbol else {"symbol": symbol, "limit": limit}
        return await call("futures-usds", "get-funding-rate-history", **params, **kw)

    @staticmethod
    async def account_balance(**kw) -> list:
        return await call("futures-usds", "futures-account-balance-v2", **kw)

    @staticmethod
    async def position(symbol: Optional[str] = None, **kw) -> list:
        params = {} if not symbol else {"symbol": symbol}
        return await call("futures-usds", "position-information-v2", **params, **kw)

    @staticmethod
    async def new_order(
        symbol: str, side: str, type_: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        test: bool = False,
        **kw,
    ) -> dict:
        cmd = "test-order" if test else "new-order"
        params = {
            "symbol": symbol, "side": side, "type": type_,
            "quantity": quantity, "time_in_force": time_in_force,
            "reduce_only": reduce_only,
        }
        if price is not None:
            params["price"] = price
        params.update(kw)
        return await call("futures-usds", cmd, **params)

    @staticmethod
    async def cancel_order(symbol: str, order_id: Optional[int] = None,
                           client_order_id: Optional[str] = None, **kw) -> dict:
        params = {"symbol": symbol}
        if order_id is not None:
            params["order_id"] = order_id
        if client_order_id:
            params["orig_client_order_id"] = client_order_id
        params.update(kw)
        return await call("futures-usds", "cancel-order", **params)

    @staticmethod
    async def cancel_all(symbol: str, **kw) -> dict:
        return await call("futures-usds", "cancel-all-open-orders", symbol=symbol, **kw)

    @staticmethod
    async def set_leverage(symbol: str, leverage: int, **kw) -> dict:
        return await call("futures-usds", "change-initial-leverage",
                          symbol=symbol, leverage=leverage, **kw)

    @staticmethod
    async def set_margin_type(symbol: str, margin_type: str, **kw) -> dict:
        return await call("futures-usds", "change-margin-type",
                          symbol=symbol, margin_type=margin_type, **kw)


class FuturesUSDSStreams:
    """USDT 永续合约 WebSocket 行情 (futures-usds-streams)"""
    module = "futures-usds-streams"

    @staticmethod
    async def kline(symbol: str, interval: str, **kw) -> str:
        """K线流,返回持续输出,需要 stream 处理"""
        return await call("futures-usds-streams", "kline-candlestick-streams",
                          symbol=symbol, interval=interval, parse_json=False, **kw)

    @staticmethod
    async def depth(symbol: str, update_speed: str = "1000ms", **kw) -> str:
        return await call("futures-usds-streams", "diff-book-depth-streams",
                          symbol=symbol, update_speed=update_speed, parse_json=False, **kw)

    @staticmethod
    async def mark_price(symbol: Optional[str] = None,
                         update_speed: str = "1000ms", **kw) -> str:
        params = {"update_speed": update_speed}
        if symbol:
            params["symbol"] = symbol
        return await call("futures-usds-streams", "mark-price-stream",
                          parse_json=False, **params, **kw)


# ==================== 单独运行测试 ====================
if __name__ == "__main__":
    """单独跑这个文件:测试 L0 适配层是否正常"""
    import sys

    print("🔍 L0 适配层测试\n")

    if not _is_installed():
        print("❌ binance-cli 未安装")
        print("   请运行: npm install -g @binance/binance-cli")
        sys.exit(1)

    print(f"✅ binance-cli 路径: {BINANCE_CLI}\n")

    async def test():
        # 1. 测试连通性
        print("1️⃣  test-connectivity ...")
        try:
            r = await call("futures-usds", "test-connectivity", parse_json=False)
            print(f"   ✅ {r}\n")
        except Exception as e:
            print(f"   ❌ {e}\n")

        # 2. 测试 ticker
        print("2️⃣  BTCUSDT 24h ticker ...")
        try:
            r = await FuturesUSDS.ticker_24h("BTCUSDT")
            print(f"   ✅ 价格: {r.get('lastPrice', 'N/A')}, 24h%: {r.get('priceChangePercent', 'N/A')}\n")
        except Exception as e:
            print(f"   ❌ {e}\n")

        # 3. 测试 K线
        print("3️⃣  BTCUSDT 1h K线 (3 根) ...")
        try:
            r = await FuturesUSDS.kline("BTCUSDT", "1h", limit=3)
            print(f"   ✅ 拿到 {len(r)} 根 K 线,第一根: {r[0][:6]}\n")
        except Exception as e:
            print(f"   ❌ {e}\n")

    asyncio.run(test())
    print("🎉 L0 测试完成")
