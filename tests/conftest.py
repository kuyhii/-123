"""
tests/conftest.py - pytest 公共 fixture
"""
import sys
from pathlib import Path
import pytest

# 把项目根加入 sys.path(让 src.* 可被 import)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture
def project_root():
    return _PROJECT_ROOT


@pytest.fixture
def sample_klines():
    """生成 30 根假 K 线(用于测试指标和策略)"""
    from src.data.models import Kline
    base = 100
    klines = []
    for i in range(30):
        # 前 10 根横盘,后 20 根单边上涨
        delta = 0.1 if i < 10 else 2.0
        base += delta
        klines.append(Kline(
            open_time=i * 60000,
            open=base, high=base + 0.5, low=base - 0.5, close=base,
            volume=100, close_time=(i + 1) * 60000, symbol="TESTUSDT"
        ))
    return klines
