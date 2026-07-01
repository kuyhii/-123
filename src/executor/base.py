"""
src/executor/base.py - 执行器抽象接口

所有执行器(真实/模拟)都实现这个接口,业务代码不感知差异。
"""
import sys
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# 让 `python src/executor/base.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.data.models import Order, OrderType, Side


class ExecutorType(str, Enum):
    """执行器类型"""
    LIVE = "LIVE"           # 真实下单
    PAPER = "PAPER"         # 本地模拟


class ExecutorMode(str, Enum):
    """用户感知的模式"""
    LIVE = "live"           # 真金白银
    PAPER = "paper"         # 模拟


@dataclass
class ExecutionResult:
    """统一的下单结果"""
    success: bool
    order_id: Optional[str] = None
    filled_qty: float = 0.0
    avg_price: float = 0.0
    fee: float = 0.0
    error: str = ""
    raw: dict = None      # 原始响应(调试用)

    def __str__(self):
        if self.success:
            return f"✅ 成交: order_id={self.order_id} filled={self.filled_qty} @ {self.avg_price}"
        return f"❌ 失败: {self.error}"


class OrderExecutor(ABC):
    """执行器抽象基类"""

    @property
    @abstractmethod
    def mode(self) -> ExecutorMode:
        """LIVE 或 PAPER"""
        pass

    @property
    @abstractmethod
    def is_real_money(self) -> bool:
        """是否动真钱"""
        pass

    @abstractmethod
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
        """下单个订单"""
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> ExecutionResult:
        """撤单"""
        pass

    @abstractmethod
    async def cancel_all(self, symbol: str) -> ExecutionResult:
        """撤销某交易对全部挂单"""
        pass

    @abstractmethod
    async def get_balance(self) -> dict:
        """查询余额(USDT)"""
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[dict]:
        """查询某交易对持仓"""
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """查询挂单"""
        pass

    def pre_trade_check(self, signal, account_equity: float) -> tuple:
        """
        下单前检查(风控层在前面,这里只做执行器特定的)

        Returns:
            (ok, reason)
        """
        return True, ""

    def __str__(self):
        money = "💰 真金" if self.is_real_money else "🎮 模拟"
        return f"{self.__class__.__name__}({self.mode.value}, {money})"
