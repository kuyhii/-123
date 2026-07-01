"""
src/storage/db.py - 持久化层

SQLite 存储:
- 行情历史(K线)
- 订单/成交记录
- 策略信号
- 账户状态快照

设计:
- 单一文件 ./data/quant.db
- 启动时自动建表
- repository 模式(数据访问逻辑独立)
"""
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from src.config import PROJECT_ROOT
from src.logger import get_logger

log = get_logger("storage")

DB_PATH = PROJECT_ROOT / "data" / "quant.db"


# ==================== Schema ====================

SCHEMA = """
CREATE TABLE IF NOT EXISTS klines (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    open_time INTEGER NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, close_time INTEGER,
    quote_volume REAL DEFAULT 0,
    trades INTEGER DEFAULT 0,
    PRIMARY KEY (symbol, interval, open_time)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT, type TEXT,
    quantity REAL, price REAL,
    status TEXT, filled_qty REAL DEFAULT 0,
    avg_price REAL DEFAULT 0,
    create_time INTEGER, update_time INTEGER
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT,
    quantity REAL,
    price REAL,
    reason TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    ts INTEGER PRIMARY KEY,
    total_equity REAL,
    available_balance REAL,
    unrealized_pnl REAL,
    positions TEXT
);

CREATE TABLE IF NOT EXISTS trade_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT,
    quantity REAL,
    price REAL,
    realized_pnl REAL,
    fee REAL,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_klines_sym_int_time
    ON klines (symbol, interval, open_time DESC);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals (ts DESC);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders (symbol, create_time DESC);
"""


# ==================== Connection 管理 ====================

@contextmanager
def get_conn():
    """获取 SQLite 连接(自动 init)"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化所有表(幂等)"""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    log.info(f"DB initialized: {DB_PATH}")


# ==================== Repository ====================

class KlinesRepository:
    """K线持久化"""

    def upsert(self, klines: List) -> int:
        if not klines:
            return 0
        with get_conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO klines
                (symbol, interval, open_time, open, high, low, close,
                 volume, close_time, quote_volume, trades)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [(k.symbol, k.interval if hasattr(k, 'interval') else "1m",
                  k.open_time, k.open, k.high, k.low, k.close,
                  k.volume, k.close_time, k.quote_volume, k.trades)
                 for k in klines]
            )
        return len(klines)

    def query(self, symbol: str, interval: str,
              start: Optional[int] = None,
              end: Optional[int] = None,
              limit: int = 1000) -> List:
        sql = "SELECT * FROM klines WHERE symbol=? AND interval=?"
        params = [symbol, interval]
        if start:
            sql += " AND open_time >= ?"
            params.append(start)
        if end:
            sql += " AND open_time <= ?"
            params.append(end)
        sql += " ORDER BY open_time DESC LIMIT ?"
        params.append(limit)
        with get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_kline(r) for r in rows]

    def count(self, symbol: str, interval: str) -> int:
        with get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM klines WHERE symbol=? AND interval=?",
                (symbol, interval)
            ).fetchone()[0]


class SignalsRepository:
    """信号日志"""

    def log(self, signal) -> int:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO signals (ts, symbol, side, quantity, price, reason, metadata)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    int(datetime.now().timestamp() * 1000),
                    signal.symbol, signal.side.value, signal.quantity,
                    signal.price, signal.reason,
                    json.dumps(signal.metadata or {}),
                ),
            )
            return cur.lastrowid

    def recent(self, limit: int = 50, symbol: Optional[str] = None) -> List[dict]:
        sql = "SELECT * FROM signals"
        params = []
        if symbol:
            sql += " WHERE symbol=?"
            params.append(symbol)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]


class OrdersRepository:
    """订单持久化"""

    def upsert(self, order) -> None:
        with get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO orders
                (order_id, symbol, side, type, quantity, price, status,
                 filled_qty, avg_price, create_time, update_time)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    order.order_id, order.symbol, order.side.value, order.type.value,
                    order.quantity, order.price, order.status,
                    order.filled_qty, order.avg_price, order.create_time, order.update_time,
                ),
            )

    def recent(self, limit: int = 50, symbol: Optional[str] = None) -> List[dict]:
        sql = "SELECT * FROM orders"
        params = []
        if symbol:
            sql += " WHERE symbol=?"
            params.append(symbol)
        sql += " ORDER BY create_time DESC LIMIT ?"
        params.append(limit)
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]


class TradesRepository:
    """成交记录"""

    def log(self, symbol: str, side: str, quantity: float,
            price: float, realized_pnl: float = 0, fee: float = 0,
            note: str = "") -> int:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO trade_journal
                (ts, symbol, side, quantity, price, realized_pnl, fee, note)
                VALUES (?,?,?,?,?,?,?,?)""",
                (int(datetime.now().timestamp() * 1000),
                 symbol, side, quantity, price, realized_pnl, fee, note)
            )
            return cur.lastrowid

    def recent(self, limit: int = 50) -> List[dict]:
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM trade_journal ORDER BY ts DESC LIMIT ?",
                (limit,)
            ).fetchall()]


# ==================== 辅助 ====================

def _row_to_kline(r) -> "Kline":
    from src.data.models import Kline
    return Kline(
        open_time=r["open_time"],
        open=r["open"], high=r["high"], low=r["low"], close=r["close"],
        volume=r["volume"],
        close_time=r["close_time"],
        quote_volume=r["quote_volume"] or 0,
        trades=r["trades"] or 0,
        symbol=r["symbol"],
    )


# ==================== 单文件测试 ====================

if __name__ == "__main__":
    print("🗄️  Storage layer test\n")
    init_db()
    print("✅ DB initialized")

    # 测试 K 线 upsert
    from src.data.models import Kline
    klines = [
        Kline(open_time=1700000000000 + i * 60000, open=100 + i, high=101 + i,
              low=99 + i, close=100.5 + i, volume=100, close_time=1700000060000 + i * 60000,
              symbol="BTCUSDT")
        for i in range(5)
    ]
    krepo = KlinesRepository()
    n = krepo.upsert(klines)
    print(f"✅ 插入 {n} 根 K线")
    queried = krepo.query("BTCUSDT", "1m", limit=10)
    print(f"✅ 查询到 {len(queried)} 根")
    print(f"   最新 close: {queried[0].close}")

    # 测试信号
    from src.data.models import Signal, Side
    srepo = SignalsRepository()
    sig = Signal("BTCUSDT", Side.BUY, 0.001, price=60000, reason="test")
    sid = srepo.log(sig)
    print(f"✅ 信号入库 ID={sid}")
    recent = srepo.recent(limit=5)
    print(f"✅ 查到 {len(recent)} 个信号")

    print(f"\n📁 DB 文件: {DB_PATH}")
