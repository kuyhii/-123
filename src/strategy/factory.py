"""
src/strategy/factory.py - 策略工厂

通过名称创建策略实例。便于:
- main.py 的 --strategy 参数支持多种策略
- 用户添加新策略只需注册,不需改 main.py
"""
import sys
from pathlib import Path
from typing import Dict, Type

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.strategy.base import Strategy


# ==================== 注册表 ====================

_REGISTRY: Dict[str, Type[Strategy]] = {}


def register(name: str):
    """装饰器:把策略类注册到工厂"""
    def decorator(cls: Type[Strategy]):
        if not issubclass(cls, Strategy):
            raise TypeError(f"{cls.__name__} must inherit Strategy")
        _REGISTRY[name] = cls
        return cls
    return decorator


def create(name: str, **params) -> Strategy:
    """通过名称创建策略实例"""
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(f"未知策略: {name!r}. 可用: {available}")
    return _REGISTRY[name](**params)


def available() -> list:
    """返回所有已注册策略名"""
    return sorted(_REGISTRY.keys())


# ==================== 自动注册已知策略 ====================

def _auto_register():
    """import 时自动注册所有内置策略

    用延迟 import 避免循环依赖
    """
    import importlib
    for mod_name in [
        "src.strategy.examples.dual_ma",
        "src.strategy.examples.multi_tf_trend",
    ]:
        importlib.import_module(mod_name)


_auto_register()


# ==================== 单独运行 ====================

if __name__ == "__main__":
    print("🏭 策略工厂\n")
    print(f"已注册策略: {available()}\n")
    for name in available():
        s = create(name)
        print(f"  {name}: {s.__class__.__name__} ({s.name})")
