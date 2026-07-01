"""
src/data/models.py - 数据类定义

所有行情、账户、订单的 dataclass 都在这里。
模块间传递用 dataclass,避免传裸 dict。
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    STOP = "STOP"
    TAKE_PROFIT = "TAKE_PROFIT"


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"  # 单向持仓模式


class MarginType(Enum):
    ISOLATED = "ISOLATED"
    CROSSED = "CROSSED"


# ==================== L1: 行情数据 ====================

@dataclass
class Kline:
    """K 线"""
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float = 0.0
    trades: int = 0
    symbol: str = ""

    @property
    def is_closed(self) -> bool:
        return True  # REST 返回的都是已收盘

    @classmethod
    def from_binance(cls, arr: list, symbol: str = "") -> "Kline":
        """binance 返回的 K 线是 [openTime, open, high, low, close, volume, closeTime, quoteVolume, trades, ...]"""
        return cls(
            open_time=int(arr[0]),
            open=float(arr[1]),
            high=float(arr[2]),
            low=float(arr[3]),
            close=float(arr[4]),
            volume=float(arr[5]),
            close_time=int(arr[6]),
            quote_volume=float(arr[7]) if len(arr) > 7 else 0.0,
            trades=int(arr[8]) if len(arr) > 8 else 0,
            symbol=symbol,
        )


@dataclass
class OrderBookLevel:
    price: float
    quantity: float

    @classmethod
    def from_binance(cls, arr: list) -> "OrderBookLevel":
        return cls(price=float(arr[0]), quantity=float(arr[1]))


@dataclass
class OrderBook:
    symbol: str
    bids: List[OrderBookLevel] = field(default_factory=list)  # 买盘,降序
    asks: List[OrderBookLevel] = field(default_factory=list)  # 卖盘,升序
    last_update_id: int = 0

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        b, a = self.best_bid, self.best_ask
        return (b + a) / 2 if b and a else None

    @property
    def spread_pct(self) -> Optional[float]:
        b, a = self.best_bid, self.best_ask
        if b and a and b > 0:
            return (a - b) / b * 100
        return None

    @classmethod
    def from_binance(cls, data: dict) -> "OrderBook":
        symbol = data.get("symbol", "")
        bids = [OrderBookLevel.from_binance(b) for b in data.get("bids", [])]
        asks = [OrderBookLevel.from_binary(a) if False else OrderBookLevel.from_binance(a) for a in data.get("asks", [])]
        return cls(
            symbol=symbol,
            bids=bids,
            asks=asks,
            last_update_id=int(data.get("lastUpdateId", 0)),
        )


@dataclass
class Ticker24h:
    """24h 行情"""
    symbol: str
    last_price: float
    price_change: float
    price_change_pct: float
    high: float
    low: float
    volume: float
    quote_volume: float

    @classmethod
    def from_binance(cls, data: dict) -> "Ticker24h":
        return cls(
            symbol=data.get("symbol", ""),
            last_price=float(data.get("lastPrice", 0)),
            price_change=float(data.get("priceChange", 0)),
            price_change_pct=float(data.get("priceChangePercent", 0)),
            high=float(data.get("highPrice", 0)),
            low=float(data.get("lowPrice", 0)),
            volume=float(data.get("volume", 0)),
            quote_volume=float(data.get("quoteVolume", 0)),
        )


@dataclass
class MarkPrice:
    symbol: str
    mark_price: float
    index_price: float
    funding_rate: float
    next_funding_time: int

    @classmethod
    def from_binance(cls, data: dict) -> "MarkPrice":
        return cls(
            symbol=data.get("symbol", ""),
            mark_price=float(data.get("markPrice", 0)),
            index_price=float(data.get("indexPrice", 0)),
            funding_rate=float(data.get("lastFundingRate", 0)),
            next_funding_time=int(data.get("nextFundingTime", 0)),
        )


# ==================== L2: 账户数据 ====================

@dataclass
class Balance:
    asset: str
    balance: float
    available_balance: float
    cross_wallet_balance: float = 0.0
    unrealized_pnl: float = 0.0

    @classmethod
    def from_binance(cls, data: dict) -> "Balance":
        return cls(
            asset=data.get("asset", ""),
            balance=float(data.get("balance", 0)),
            available_balance=float(data.get("availableBalance", 0)),
            cross_wallet_balance=float(data.get("crossWalletBalance", 0)),
            unrealized_pnl=float(data.get("crossUnPnl", 0)),
        )


@dataclass
class Position:
    symbol: str
    side: PositionSide
    quantity: float         # 持仓数量(带符号:正=多,负=空)
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int
    margin_type: MarginType
    liquidation_price: float = 0.0

    @property
    def notional(self) -> float:
        return abs(self.quantity) * self.mark_price

    @property
    def margin(self) -> float:
        return self.notional / self.leverage if self.leverage else 0

    @classmethod
    def from_binance(cls, data: dict) -> Optional["Position"]:
        amt = float(data.get("positionAmt", 0))
        if amt == 0:
            return None
        side = PositionSide.LONG if amt > 0 else PositionSide.SHORT
        return cls(
            symbol=data.get("symbol", ""),
            side=side,
            quantity=amt,
            entry_price=float(data.get("entryPrice", 0)),
            mark_price=float(data.get("markPrice", 0)),
            unrealized_pnl=float(data.get("unRealizedProfit", 0)),
            leverage=int(data.get("leverage", 1)),
            margin_type=MarginType(data.get("marginType", "ISOLATED")),
            liquidation_price=float(data.get("liquidationPrice", 0)),
        )


@dataclass
class Order:
    symbol: str
    order_id: int
    side: Side
    type: OrderType
    quantity: float
    price: float
    status: str
    filled_qty: float = 0.0
    avg_price: float = 0.0
    create_time: int = 0
    update_time: int = 0

    @property
    def is_filled(self) -> bool:
        return self.status == "FILLED"

    @property
    def is_open(self) -> bool:
        return self.status in ("NEW", "PARTIALLY_FILLED")

    @classmethod
    def from_binance(cls, data: dict) -> "Order":
        return cls(
            symbol=data.get("symbol", ""),
            order_id=int(data.get("orderId", 0)),
            side=Side(data.get("side", "BUY")),
            type=OrderType(data.get("type", "LIMIT")),
            quantity=float(data.get("origQty", 0)),
            price=float(data.get("price", 0)),
            status=data.get("status", ""),
            filled_qty=float(data.get("executedQty", 0)),
            avg_price=float(data.get("avgPrice", 0)),
            create_time=int(data.get("time", 0)),
            update_time=int(data.get("updateTime", 0)),
        )


# ==================== L5: 策略信号 ====================

@dataclass
class Signal:
    """策略产生的交易信号"""
    symbol: str
    side: Side
    quantity: float
    reason: str = ""
    price: Optional[float] = None          # None = 市价
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reduce_only: bool = False
    metadata: dict = field(default_factory=dict)

    def __str__(self):
        sl = f" SL={self.stop_loss}" if self.stop_loss else ""
        tp = f" TP={self.take_profit}" if self.take_profit else ""
        ro = " [reduce]" if self.reduce_only else ""
        return f"Signal({self.side.value} {self.symbol} qty={self.quantity} @{self.price}{sl}{tp}{ro}) [{self.reason}]"
