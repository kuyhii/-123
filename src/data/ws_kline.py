"""
src/data/ws_kline.py - L1 WebSocket K线

把 binance-cli 的 WS 长连接包装成 async generator,
业务层用 `async for kline in KlineStream.subscribe(...)` 即可。
"""
import asyncio
import json
import shlex
from typing import AsyncIterator, Optional, Callable

from src.adapter.binance_cli import BINANCE_CLI, _is_installed
from src.data.models import Kline
from src.logger import get_logger

log = get_logger("data.ws_kline")


class KlineStream:
    """K线 WebSocket 流(单 symbol)"""

    def __init__(self, symbol: str, interval: str):
        self.symbol = symbol
        self.interval = interval
        self._process: Optional[asyncio.subprocess.Process] = None

    async def subscribe(self, on_kline: Optional[Callable[[Kline], None]] = None) -> AsyncIterator[Kline]:
        """
        订阅 K线

        Args:
            on_kline: 可选回调函数,每根 K 线触发

        Yields:
            Kline 对象(包含已收盘和未收盘的 K 线)
        """
        if not _is_installed():
            raise FileNotFoundError("binance-cli 未安装")

        cmd = [BINANCE_CLI, "futures-usds-streams", "kline-candlestick-streams",
               "--symbol", self.symbol, "--interval", self.interval]

        log.info(f"启动 K线 WS: {self.symbol} {self.interval}")

        self._process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    err = await self._process.stderr.read()
                    log.error(f"K线 WS 关闭: {err.decode()[:200]}")
                    break
                try:
                    msg = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError:
                    continue

                # binance 格式: {"e": "kline", "k": {"t":.., "o":.., "h":.., "l":.., "c":.., "v":..}}
                k = msg.get("k", {})
                kline = Kline(
                    open_time=int(k.get("t", 0)),
                    open=float(k.get("o", 0)),
                    high=float(k.get("h", 0)),
                    low=float(k.get("l", 0)),
                    close=float(k.get("c", 0)),
                    volume=float(k.get("v", 0)),
                    close_time=int(k.get("T", 0)),
                    quote_volume=float(k.get("q", 0)),
                    trades=int(k.get("n", 0)),
                    symbol=self.symbol,
                )
                kline.is_closed = bool(k.get("x", False))  # x=True 表示 K 线已收盘
                if on_kline:
                    on_kline(kline)
                yield kline

        finally:
            await self.stop()

    async def stop(self):
        if self._process and self._process.returncode is None:
            log.info(f"停止 K线 WS: {self.symbol}")
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
            self._process = None


# ==================== 单独运行测试 ====================
if __name__ == "__main__":
    """单独跑:订阅 BTCUSDT 1m K线 5 次"""
    print("🔍 L1 WS K线测试\n")

    async def test():
        count = 0
        stream = KlineStream("BTCUSDT", "1m")
        try:
            async for k in stream.subscribe():
                status = "✅ 收盘" if getattr(k, "is_closed", False) else "🔄 进行中"
                print(f"{status} O={k.open} H={k.high} L={k.low} C={k.close} V={k.volume}")
                count += 1
                if count >= 3:
                    break
        except Exception as e:
            print(f"❌ {e}")

    try:
        asyncio.run(test())
        print("\n🎉 L1 WS 测试完成")
    except FileNotFoundError as e:
        print(f"❌ {e}")
