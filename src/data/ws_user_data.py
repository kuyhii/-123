"""
src/data/ws_user_data.py - L1 WebSocket 用户数据流

订阅账户余额、持仓、订单变化。
需要先通过 start-user-data-stream 拿到 listen-key。
"""
import asyncio
import json
from typing import Optional, Callable, AsyncIterator

from src.adapter.binance_cli import BINANCE_CLI, _is_installed, call
from src.logger import get_logger

log = get_logger("data.ws_userdata")


class UserDataStream:
    """用户数据 WebSocket"""

    def __init__(self):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._listen_key: Optional[str] = None

    async def _get_listen_key(self) -> str:
        """从 binance-cli 拿 listen-key"""
        result = await call("futures-usds", "start-user-data-stream")
        if isinstance(result, dict):
            self._listen_key = result.get("listenKey", "")
        else:
            self._listen_key = str(result).strip('"')
        if not self._listen_key:
            raise RuntimeError("未能获取 listenKey")
        return self._listen_key

    async def subscribe(
        self,
        on_event: Optional[Callable[[dict], None]] = None
    ) -> AsyncIterator[dict]:
        """
        订阅用户数据

        事件类型:
        - ACCOUNT_UPDATE: 余额/持仓变化
        - ORDER_TRADE_UPDATE: 订单/成交回报
        """
        if not _is_installed():
            raise FileNotFoundError("binance-cli 未安装")

        listen_key = await self._get_listen_key()
        log.info(f"启动 user-data WS (listen-key: {listen_key[:8]}...)")

        cmd = [BINANCE_CLI, "futures-usds-streams", "user-data",
               "--listen-key", listen_key]
        self._process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError:
                    continue
                if on_event:
                    on_event(msg)
                yield msg
        finally:
            await self.stop()

    async def stop(self):
        if self._process and self._process.returncode is None:
            log.info("停止 user-data WS")
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
            self._process = None
        if self._listen_key:
            try:
                await call("futures-usds", "close-user-data-stream")
            except Exception:
                pass
            self._listen_key = None


if __name__ == "__main__":
    print("🔍 user-data WS 测试(需要 API key)\n")

    async def test():
        try:
            stream = UserDataStream()
            count = 0
            async for event in stream.subscribe():
                e = event.get("e", "?")
                print(f"event: {e}")
                count += 1
                if count >= 2:
                    break
        except FileNotFoundError as e:
            print(f"❌ {e}")
        except Exception as e:
            print(f"❌ {e}")

    try:
        asyncio.run(test())
    except Exception as e:
        print(f"❌ {e}")
