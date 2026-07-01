"""
src/data/indicators.py - 增强技术指标

v0.5 的 sma/ema/rsi 在 market_data.py,这里把全部技术指标集中:
- MACD(异同移动平均)
- 布林带(Bollinger Bands)
- ATR(平均真实波幅)
- KDJ(随机指标)
- OBV(能量潮)
- 成交量均线

所有指标都返回简单 dataclass,不依赖 pandas。
"""
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ==================== MACD ====================

@dataclass
class MACD:
    macd: float           # 短期 EMA - 长期 EMA
    signal: float         # MACD 的 N 日 EMA
    histogram: float      # macd - signal

    def is_bullish_cross(self, prev: "MACD") -> bool:
        """金叉:前一根 histogram<=0,当前>0"""
        return prev.histogram <= 0 < self.histogram

    def is_bearish_cross(self, prev: "MACD") -> bool:
        """死叉"""
        return prev.histogram >= 0 > self.histogram


def macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[MACD]:
    """MACD 指标(最后一点的值)"""
    if len(closes) < slow + signal:
        return None
    # 计算 EMA 序列(前面有 None 占位,长度 == closes 长度)
    fast_ema = _ema_series(closes, fast)
    slow_ema = _ema_series(closes, slow)
    # 截掉前面的 None
    fast_ema_vals = [x for x in fast_ema if x is not None]
    slow_ema_vals = [x for x in slow_ema if x is not None]
    if not fast_ema_vals or not slow_ema_vals:
        return None
    # 对齐到相同长度(用末尾对齐)
    n = min(len(fast_ema_vals), len(slow_ema_vals))
    diff = [f - s for f, s in zip(fast_ema_vals[-n:], slow_ema_vals[-n:])]
    sig = _ema_series(diff, signal)
    sig_vals = [x for x in sig if x is not None]
    if not sig_vals:
        return None
    h = diff[-1] - sig_vals[-1]
    return MACD(macd=diff[-1], signal=sig_vals[-1], histogram=h)


def macd_series(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> List[MACD]:
    """MACD 完整序列"""
    if len(closes) < slow + signal:
        return []
    fast_ema = _ema_series(closes, fast)
    slow_ema = _ema_series(closes, slow)
    if not fast_ema or not slow_ema:
        return []
    n = min(len(fast_ema), len(slow_ema))
    diff = [f - s for f, s in zip(fast_ema[-n:], slow_ema[-n:])]
    sig = _ema_series(diff, signal)
    if not sig:
        return []
    out = []
    for i in range(len(sig)):
        out.append(MACD(macd=diff[i + (len(diff) - len(sig))],
                        signal=sig[i],
                        histogram=diff[i + (len(diff) - len(sig))] - sig[i]))
    return out


# ==================== Bollinger Bands ====================

@dataclass
class BollingerBands:
    upper: float     # 上轨
    middle: float    # 中轨(SMA)
    lower: float     # 下轨
    bandwidth: float  # (upper - lower) / middle
    percent_b: float  # (price - lower) / (upper - lower),0=下轨,1=上轨

    @property
    def is_squeeze(self) -> bool:
        """布林带收窄 → 可能突破"""
        return self.bandwidth < 0.02  # 阈值可调


def bollinger(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Optional[BollingerBands]:
    """布林带"""
    if len(closes) < period:
        return None
    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((c - middle) ** 2 for c in window) / period
    std = variance ** 0.5
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    bandwidth = (upper - lower) / middle if middle else 0
    price = closes[-1]
    pct_b = (price - lower) / (upper - lower) if upper > lower else 0
    return BollingerBands(upper=upper, middle=middle, lower=lower,
                          bandwidth=bandwidth, percent_b=pct_b)


# ==================== ATR ====================

@dataclass
class ATR:
    value: float
    trend: str  # "up" / "down" / "flat"

    def is_high_volatility(self, threshold: float = 0.03) -> bool:
        """高波动"""
        return self.value > threshold


def atr(klines_data: List[dict], period: int = 14) -> Optional[ATR]:
    """
    平均真实波幅

    klines_data: 包含 high/low/close 的字典列表
    """
    if len(klines_data) < period + 1:
        return None

    trs = []
    for i in range(1, len(klines_data)):
        h = klines_data[i]["high"]
        l = klines_data[i]["low"]
        pc = klines_data[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)

    if len(trs) < period:
        return None

    # 简单移动平均
    atr_val = sum(trs[-period:]) / period

    # 趋势判断
    if len(klines_data) >= 2:
        last_close = klines_data[-1]["close"]
        prev_close = klines_data[-2]["close"]
        if last_close > prev_close:
            trend = "up"
        elif last_close < prev_close:
            trend = "down"
        else:
            trend = "flat"
    else:
        trend = "flat"

    return ATR(value=atr_val, trend=trend)


# ==================== KDJ ====================

@dataclass
class KDJ:
    k: float
    d: float
    j: float

    def is_golden_cross(self, prev: "KDJ") -> bool:
        """K 上穿 D"""
        return prev.k <= prev.d and self.k > self.d

    def is_death_cross(self, prev: "KDJ") -> bool:
        return prev.k >= prev.d and self.k < self.d

    def is_oversold(self) -> bool:
        return self.k < 20 and self.d < 20

    def is_overbought(self) -> bool:
        return self.k > 80 and self.d > 80


def kdj(highs: List[float], lows: List[float], closes: List[float],
        n: int = 9, m1: int = 3, m2: int = 3) -> Optional[KDJ]:
    """KDJ 随机指标"""
    if len(closes) < n:
        return None

    k_prev, d_prev = 50, 50  # 初始值
    for i in range(n - 1, len(closes)):
        hn = max(highs[i - n + 1:i + 1])
        ln = min(lows[i - n + 1:i + 1])
        rsv = (closes[i] - ln) / (hn - ln) * 100 if hn > ln else 50
        k = (m1 - 1) / m1 * k_prev + 1 / m1 * rsv
        d = (m2 - 1) / m2 * d_prev + 1 / m2 * k
        j = 3 * k - 2 * d
        k_prev, d_prev = k, d

    return KDJ(k=k_prev, d=d_prev, j=j)


# ==================== OBV ====================

def obv(closes: List[float], volumes: List[float]) -> List[float]:
    """能量潮指标"""
    if len(closes) != len(volumes) or len(closes) < 2:
        return []
    out = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            out.append(out[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            out.append(out[-1] - volumes[i])
        else:
            out.append(out[-1])
    return out


def obv_sma(volumes: List[float], closes: List[float], period: int = 20) -> Optional[float]:
    """OBV 的 SMA"""
    obv_vals = obv(closes, volumes)
    if len(obv_vals) < period:
        return None
    return sum(obv_vals[-period:]) / period


# ==================== 内部辅助 ====================

def _ema_series(values: List[float], period: int) -> List[Optional[float]]:
    """完整 EMA 序列"""
    if len(values) < period:
        return [None] * len(values)
    k = 2.0 / (period + 1)
    out = [None] * (period - 1)
    ema = sum(values[:period]) / period
    out.append(ema)
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
        out.append(ema)
    return out


# ==================== 单独测试 ====================

if __name__ == "__main__":
    print("📊 技术指标测试\n")

    closes = [100 + i * 0.5 for i in range(60)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    volumes = [1000] * 60

    # MACD
    m = macd(closes)
    print(f"MACD: macd={m.macd:.4f} signal={m.signal:.4f} hist={m.histogram:.4f}")

    # Bollinger
    bb = bollinger(closes, period=20)
    print(f"布林带: upper={bb.upper:.2f} middle={bb.middle:.2f} lower={bb.lower:.2f}")
    print(f"        bandwidth={bb.bandwidth:.4f} %B={bb.percent_b:.2f}")

    # ATR
    kd = [{"high": h, "low": l, "close": c} for h, l, c in zip(highs, lows, closes)]
    a = atr(kd, period=14)
    print(f"ATR: value={a.value:.4f} trend={a.trend}")

    # KDJ
    k = kdj(highs, lows, closes)
    print(f"KDJ: K={k.k:.2f} D={k.d:.2f} J={k.j:.2f}")

    # OBV
    o = obv(closes, volumes)
    print(f"OBV: 当前值={o[-1]:.0f}, 长度={len(o)}")

    print("\n🎉 全部指标计算完成")
