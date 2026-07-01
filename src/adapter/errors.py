"""
src/adapter/errors.py - 异常体系

所有 binance-cli 调用可能抛出的异常,统一在这里定义。
"""
from typing import Optional


class BinanceCLIError(Exception):
    """binance-cli 调用错误基类"""
    def __init__(self, message: str, exit_code: int = -1, stderr: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


class BinanceAuthError(BinanceCLIError):
    """认证错误(API key 错、签名错)"""
    pass


class BinanceRateLimitError(BinanceCLIError):
    """限流(429)"""
    pass


class BinanceNetworkError(BinanceCLIError):
    """网络错误(超时、连接失败)"""
    pass


class BinanceAPIError(BinanceCLIError):
    """Binance API 业务错误(余额不足、参数错等)"""
    def __init__(self, message: str, exit_code: int = -1, stderr: str = "",
                 code: Optional[int] = None):
        super().__init__(message, exit_code, stderr)
        self.code = code


def classify_error(stderr: str, exit_code: int) -> BinanceCLIError:
    """根据 stderr 内容分类错误"""
    s = stderr.lower()
    if "invalid api-key" in s or "signature" in s or "unauthorized" in s:
        return BinanceAuthError("API 认证失败", exit_code, stderr)
    if "rate limit" in s or "too many requests" in s or "429" in s:
        return BinanceRateLimitError("触发限流", exit_code, stderr)
    if "timeout" in s or "econnrefused" in s or "enotfound" in s:
        return BinanceNetworkError("网络错误", exit_code, stderr)
    return BinanceAPIError(stderr[:200] if stderr else "未知错误", exit_code, stderr)
