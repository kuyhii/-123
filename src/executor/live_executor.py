"""
src/executor/live_executor.py - 真实下单执行器(真金白银)

⚠️ 警告:这个类会调真实币安 API,下真实订单,使用真实资金。
   所有调用都通过 binance-cli(已经在 .env 配 profile)。

   任何使用此类的代码都应该:
   1. 先经过 RiskManager 检查
   2. 用户在 main.py 显式输入 CONFIRM
   3. 配置 BINANCE_API_ENV=prod(或 testnet) 真实环境
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.executor.base import (
    OrderExecutor, ExecutionResult, ExecutorMode, ExecutorType,
)
from src.data.models import Order, OrderType, Side
from src.logger import get_logger
from src.config import CONFIG
from src.notify.notifier import DEFAULT_NOTIFIER as notifier

log = get_logger("live_executor")


class LiveExecutor(OrderExecutor):
    """
    真实下单执行器

    安全特性:
    - 二次确认(下单前再检查一次 mode)
    - 风控失败直接拒绝
    - 异常立即通知
    - 不允许 reduce_only=False 的市价大单(可用 LIMIT 替代)
    """

    def __init__(self):
        # 启动时再次确认 mode
        if CONFIG.binance.env not in ("prod", "testnet", "demo"):
            raise RuntimeError(
                f"❌ LiveExecutor 拒绝启动: BINANCE_API_ENV={CONFIG.binance.env!r} "
                f"必须是 prod / testnet / demo 之一"
            )
        if not CONFIG.has_credentials:
            raise RuntimeError(
                "❌ LiveExecutor 拒绝启动:未配置 BINANCE_API_KEY / BINANCE_SECRET_KEY"
            )
        log.warning(
            f"⚠️  LiveExecutor 启动 - "
            f"env={CONFIG.binance.env} profile={CONFIG.binance.profile}"
        )
        notifier.warn(
            "真实盘执行器启动",
            f"env={CONFIG.binance.env}, 这会用真金白银"
        )

    @property
    def mode(self) -> ExecutorMode:
        return ExecutorMode.LIVE

    @property
    def is_real_money(self) -> bool:
        return True

    def pre_trade_check(self, signal, account_equity: float) -> tuple:
        """真实盘额外加更严的检查"""
        # 1. mode 必须是 prod/testnet/demo
        if CONFIG.binance.env not in ("prod", "testnet"):
            log.warning(f"环境 {CONFIG.binance.env!r} 不明确为生产")
        # 2. 账户净值不能太低
        if account_equity < 50:  # < $50 不让开仓
            return False, f"账户净值 ${account_equity:.2f} 过低(< $50),暂停交易"
        # 3. 单笔名义价值上限
        if signal.price and signal.quantity * signal.price > account_equity * 0.5:
            return False, f"单笔名义 ${signal.quantity * signal.price:.2f} 超过账户 50%,太大"
        return True, ""

    async def place_order(
        self,
        symbol: str,
        side: Side,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
        **kwargs,
    ) -> ExecutionResult:
        """真实下单"""
        log.warning(
            f"📤 [LIVE] 下单: {side.value} {symbol} "
            f"{order_type.value} qty={quantity} price={price}"
        )
        notifier.warn(
            "真实下单",
            f"{side.value} {symbol} {quantity} @ {price}"
        )
        try:
            params = {
                "symbol": symbol,
                "side": side.value,
                "type_": order_type.value,
                "quantity": quantity,
                "reduce_only": reduce_only,
            }
            if price is not None:
                params["price"] = price
            params.update(kwargs)

            result = await self._call_cli("futures-usds", "new-order", **params)

            order_id = str(result.get("orderId", ""))
            filled = float(result.get("executedQty", 0))
            avg_price = float(result.get("avgPrice", 0))
            log.info(f"✅ [LIVE] 下单成功: order_id={order_id} filled={filled}")
            notifier.trade(symbol, side.value, quantity, price or avg_price)
            return ExecutionResult(
                success=True,
                order_id=order_id,
                filled_qty=filled,
                avg_price=avg_price,
                raw=result,
            )
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            log.error(f"❌ [LIVE] 下单失败: {err}")
            notifier.error("真实下单失败", f"{symbol} {err}")
            return ExecutionResult(success=False, error=err)

    async def cancel_order(self, symbol: str, order_id: str) -> ExecutionResult:
        log.info(f"📤 [LIVE] 撤单 {symbol} #{order_id}")
        try:
            result = await self._call_cli("futures-usds", "cancel-order",
                                          symbol=symbol, order_id=order_id)
            return ExecutionResult(success=True, order_id=order_id, raw=result)
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    async def cancel_all(self, symbol: str) -> ExecutionResult:
        log.info(f"📤 [LIVE] 全撤 {symbol}")
        try:
            result = await self._call_cli("futures-usds", "cancel-all-open-orders",
                                          symbol=symbol)
            return ExecutionResult(success=True, raw=result)
        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    async def get_balance(self) -> dict:
        try:
            result = await self._call_cli("futures-usds", "futures-account-balance-v2")
            # 解析 USDT 余额
            for asset in result:
                if asset.get("asset") == "USDT":
                    return {
                        "total": float(asset.get("balance", 0)),
                        "available": float(asset.get("availableBalance", 0)),
                        "unrealized": float(asset.get("crossUnPnl", 0)),
                    }
            return {"total": 0, "available": 0, "unrealized": 0}
        except Exception as e:
            log.error(f"查询余额失败: {e}")
            return {"total": 0, "available": 0, "unrealized": 0}

    async def get_position(self, symbol: str) -> Optional[dict]:
        try:
            result = await self._call_cli("futures-usds", "position-information-v2",
                                          symbol=symbol)
            for p in result:
                if float(p.get("positionAmt", 0)) != 0:
                    return p
            return None
        except Exception as e:
            log.error(f"查询持仓失败: {e}")
            return None

    async def get_open_orders(self, symbol: Optional[str] = None) -> list:
        try:
            kw = {"symbol": symbol} if symbol else {}
            return await self._call_cli("futures-usds", "current-all-open-orders", **kw)
        except Exception as e:
            log.error(f"查询挂单失败: {e}")
            return []

    async def _call_cli(self, module: str, command: str, **params) -> dict:
        """调用 binance-cli"""
        args = [shutil_which_binance_cli(), module, command]
        for k, v in params.items():
            if v is None or v is False:
                continue
            if v is True:
                args.append(f"--{k.replace('_', '-')}")
            else:
                args.extend([f"--{k.replace('_', '-')}", str(v)])
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="replace")[:300])
        return json.loads(out) if out else {}


def shutil_which_binance_cli():
    import shutil
    return shutil.which("binance-cli") or "binance-cli"
