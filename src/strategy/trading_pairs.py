"""
src/strategy/trading_pairs.py - 交易品种池管理

职责:
- 启动时加载 config/trading_pairs.json
- 提供刷新函数(从币安拉最新交易量,过滤后取前 N)
- 提供校验函数(币种是否在池中)
- 提供 list 迭代器供策略用
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# 让 `python src/strategy/trading_pairs.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import CONFIG, PROJECT_ROOT
from src.logger import get_logger

log = get_logger("trading_pairs")


# ==================== 文件 IO ====================

def get_pairs_path() -> Path:
    """获取交易对文件路径"""
    p = Path(CONFIG.pool.file)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def load_pairs() -> List[str]:
    """
    从 json 加载当前交易对列表

    失败时返回空列表(让上层决定如何处理)
    """
    path = get_pairs_path()
    if not path.exists():
        log.warning(f"交易对文件不存在: {path}")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        symbols = data.get("symbols", [])
        updated = data.get("updated_at", "unknown")
        log.info(f"从 {path.name} 加载 {len(symbols)} 个交易对 (更新于 {updated})")
        return symbols
    except Exception as e:
        log.error(f"解析 {path} 失败: {e}")
        return []


def load_metadata() -> dict:
    """加载完整元数据(交易量、更新时间和币种列表)"""
    path = get_pairs_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def in_pairs(symbol: str) -> bool:
    """某币种是否在池中"""
    return symbol in load_pairs()


# ==================== 刷新逻辑 ====================

def refresh_pairs(top_n: int = None) -> List[str]:
    """
    从币安拉最新 USDT 加密币永续合约,按 24h 交易量排序,取前 N(默认 40)。

    排除:
    - 非 TRADING 状态
    - 非 USDT 报价
    - underlyingSubType 含 TradFi(股票/实物贵金属/原油)

    写回配置文件,含交易量快照。
    """
    if top_n is None:
        top_n = CONFIG.pool.top_n
    log.info(f"开始刷新交易对池(top {top_n})...")

    # 1. 拉 exchange-info
    r = subprocess.run(
        ["binance-cli", "futures-usds", "exchange-information"],
        capture_output=True, text=True, shell=True
    )
    if r.returncode != 0:
        log.error(f"exchange-information 失败: {r.stderr[:200]}")
        return []
    info = json.loads(r.stdout)
    symbols_info = info.get("symbols", [])

    # 2. 过滤
    crypto_usdt = []
    for s in symbols_info:
        if s.get("status") != "TRADING":
            continue
        if not s["symbol"].endswith("USDT"):
            continue
        if "TradFi" in s.get("underlyingSubType", []):
            continue
        crypto_usdt.append(s["symbol"])
    log.info(f"过滤后 {len(crypto_usdt)} 个 USDT 加密币交易对")

    # 3. 拉 24h ticker
    r = subprocess.run(
        ["binance-cli", "futures-usds", "ticker24hr-price-change-statistics"],
        capture_output=True, text=True, shell=True
    )
    if r.returncode != 0:
        log.error(f"ticker 失败: {r.stderr[:200]}")
        return []
    tickers = json.loads(r.stdout)
    vol_map = {t["symbol"]: float(t.get("quoteVolume", 0)) for t in tickers}

    # 4. 排序,取前 N
    crypto_usdt.sort(key=lambda sym: vol_map.get(sym, 0), reverse=True)
    top = crypto_usdt[:top_n]

    # 5. 写回
    path = get_pairs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": "binance futures-usds exchange-information + ticker24hr",
                "criteria": (
                    f"Top {top_n} by 24h quote volume, "
                    "USDT-margined, TRADING status, exclude underlyingSubType=TradFi"
                ),
                "count": len(top),
                "symbols": top,
                "volumes_24h_usdt": {sym: vol_map[sym] for sym in top},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info(f"✅ 已写入 {path} ({len(top)} 个币种,最小交易量 {vol_map[top[-1]]:.0f} USDT)")
    return top


def get_diff_report(old: List[str], new: List[str]) -> dict:
    """对比新旧池子,生成增减报告"""
    old_set, new_set = set(old), set(new)
    return {
        "added": sorted(new_set - old_set),
        "removed": sorted(old_set - new_set),
        "kept": sorted(old_set & new_set),
    }


# ==================== 单独运行 ====================

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="交易品种池管理")
    p.add_argument("--refresh", action="store_true", help="从币安拉最新刷新")
    p.add_argument("--show", action="store_true", help="显示当前池")
    p.add_argument("--top", type=int, default=None, help=f"刷新的 top N(默认 {CONFIG.pool.top_n})")
    args = p.parse_args()

    if args.refresh:
        old = load_pairs()
        pool = refresh_pairs(args.top)
        diff = get_diff_report(old, pool)
        print()
        print(f"📊 更新完成,共 {len(pool)} 个币种")
        if diff["added"]:
            print(f"   ➕ 新增({len(diff['added'])}): {', '.join(diff['added'][:5])}...")
        if diff["removed"]:
            print(f"   ➖ 剔除({len(diff['removed'])}): {', '.join(diff['removed'][:5])}...")
        if not diff["added"] and not diff["removed"]:
            print("   (无变化)")
        print()
        for i, sym in enumerate(pool, 1):
            print(f"  {i:>2}. {sym}")
    else:
        pool = load_pairs()
        meta = load_metadata()
        print(f"\n📊 当前交易对池 ({len(pool)} 个):")
        print("=" * 60)
        print(f"   更新于: {meta.get('updated_at', '?')}")
        print(f"   来源:   {meta.get('source', '?')}")
        print(f"   标准:   {meta.get('criteria', '?')}")
        print("-" * 60)
        vols = meta.get("volumes_24h_usdt", {})
        for i, sym in enumerate(pool, 1):
            vol = vols.get(sym, 0)
            print(f"  {i:>2}. {sym:<14}  {vol:>15,.0f} USDT")
        print()
        print("提示: 用 --refresh 重新拉取")
