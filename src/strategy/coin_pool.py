"""
src/strategy/coin_pool.py - 交易品种池管理

职责:
- 从 config/coin_pool.json 加载币种列表
- 提供刷新币种池的工具(调用 binance-cli 拉最新交易量)
- 校验币种是否在池中

注意: src/strategy/ 之前有过 signal.py 但已删除, 因为
      它会跟标准库 `signal` 同名遮蔽, 导致 subprocess 加载失败。
      现在 Signal/Side 直接从 src.data.models 导入。
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# 让 `python src/strategy/coin_pool.py` 单独跑能找到 src
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import PROJECT_ROOT, CONFIG
from src.logger import get_logger

log = get_logger("coin_pool")


def get_pool_path() -> Path:
    return Path(CONFIG.pool.file)


def load_pool() -> List[str]:
    """从 json 加载当前币种池"""
    path = get_pool_path()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        log.warning(f"币种池文件不存在: {path}")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        symbols = data.get("symbols", [])
        log.info(f"从 {path.name} 加载 {len(symbols)} 个币种")
        return symbols
    except Exception as e:
        log.error(f"解析 {path} 失败: {e}")
        return []


def in_pool(symbol: str) -> bool:
    """某币种是否在池中"""
    return symbol in load_pool()


def refresh_pool(top_n: int = 30) -> List[str]:
    """
    从币安拉最新 USDT 加密币永续合约,按 24h 交易量排序取前 N。

    排除:
    - 非 TRADING 状态
    - 非 USDT 报价
    - underlyingSubType 含 TradFi(股票/贵金属/原油)
    """
    log.info(f"开始刷新币种池(top {top_n})...")

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

    # 3. 拉 24h ticker 拿交易量
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

    # 5. 写到 coin_pool.json
    pool_path = get_pool_path()
    if not pool_path.is_absolute():
        pool_path = PROJECT_ROOT / pool_path
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(
        json.dumps(
            {
                "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "source": "binance futures-usds exchange-information + ticker24hr",
                "filter": ["USDT quote", "TRADING status", "exclude underlyingSubType=TradFi"],
                "count": len(top),
                "symbols": top,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info(f"✅ 已写入 {pool_path} ({len(top)} 个币种)")
    return top


# ==================== 单独运行测试 ====================
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="币种池管理")
    p.add_argument("--refresh", action="store_true", help="从币安拉最新刷新池")
    p.add_argument("--show", action="store_true", help="显示当前池")
    p.add_argument("--top", type=int, default=30, help="刷新的 top N(默认 30)")
    args = p.parse_args()

    if args.refresh:
        pool = refresh_pool(args.top)
        print()
        print(f"📊 USDT 加密币永续 交易量前 {len(pool)}:")
        print("=" * 60)
        for i, sym in enumerate(pool, 1):
            print(f"  {i:>2}. {sym}")
    else:
        pool = load_pool()
        print(f"\n📊 当前币种池 ({len(pool)} 个):")
        print("=" * 60)
        for i, sym in enumerate(pool, 1):
            print(f"  {i:>2}. {sym}")
        print()
        print("提示: 用 --refresh 重新拉取")
