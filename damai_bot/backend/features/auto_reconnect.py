"""
大麦抢票系统 - 自动重连机制

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。

技术要点：
- 指数退避重试策略（Exponential Backoff with Jitter）
- 网络连接监控（aiohttp / ping 回退）
- 浏览器健康检查（页面响应性检测）
- 装饰器模式的自动重连封装

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import asyncio
import time
import random
from typing import Callable, Any, Dict, Optional
from functools import wraps

from backend.utils import log, retry_async


class AutoReconnect:
    """自动重连管理器"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 30.0, backoff_factor: float = 2.0):
        """
        :param max_retries: 最大重试次数
        :param base_delay: 基础延迟（秒）
        :param max_delay: 最大延迟（秒）
        :param backoff_factor: 退避因子
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    async def execute_with_reconnect(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行函数，失败时自动重连
        """
        last_exception = None
        delay = self.base_delay

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    log(f"第 {attempt} 次重试，等待 {delay:.2f} 秒...")
                    await asyncio.sleep(delay)

                result = await func(*args, **kwargs)
                if attempt > 0:
                    log(f"重试成功！")

                return result

            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_exception = e

                # 检查异常类型，决定是否需要重连
                if self._should_reconnect(e):
                    log(f"执行失败（尝试 {attempt + 1}/{self.max_retries + 1}）: {e}")
                    log(f"错误类型: {type(e).__name__}")

                    # 计算下一次延迟（指数退避 + 随机抖动）
                    delay = min(
                        self.max_delay,
                        delay * self.backoff_factor * (1 + random.random() * 0.1)
                    )
                else:
                    # 不可恢复的错误，直接抛出
                    log(f"不可恢复的错误: {e}")
                    raise

        # 所有重试都失败
        log(f"达到最大重试次数 ({self.max_retries})，最终失败")
        raise last_exception or Exception("重试失败")

    def _should_reconnect(self, exception: Exception) -> bool:
        """判断是否需要重连"""
        exception_str = str(exception).lower()

        # 网络相关错误
        network_errors = [
            'timeout', 'connection', 'network', 'socket', 'refused',
            'reset', 'closed', 'unreachable', 'disconnected'
        ]

        # 浏览器相关错误
        browser_errors = [
            'browser', 'context', 'page', 'playwright', 'chromium',
            'target closed', 'session', 'cookie', 'navigation'
        ]

        # 检查异常消息
        for error in network_errors + browser_errors:
            if error in exception_str:
                return True

        # 检查异常类型
        exception_type = type(exception).__name__.lower()
        for error in network_errors + browser_errors:
            if error in exception_type:
                return True

        return False

    def reconnect_decorator(self, max_retries: int = None):
        """自动重连装饰器"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                reconnect = AutoReconnect(
                    max_retries=max_retries or self.max_retries,
                    base_delay=self.base_delay,
                    max_delay=self.max_delay,
                    backoff_factor=self.backoff_factor
                )
                return await reconnect.execute_with_reconnect(func, *args, **kwargs)
            return wrapper
        return decorator


class ConnectionMonitor:
    """连接监控器"""

    def __init__(self, check_interval: float = 30.0, timeout: float = 10.0):
        self.check_interval = check_interval
        self.timeout = timeout
        self.monitoring = False
        self.last_success_time = time.time()
        self.failures = 0
        self.max_failures = 3

    async def check_connection(self, test_url: str = "https://www.baidu.com") -> bool:
        """检查网络连接"""
        try:
            # 使用 asyncio 和 aiohttp 检查连接
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(test_url) as response:
                    return response.status == 200
        except ImportError:
            # 如果没有 aiohttp，使用简单的 ping 检查
            import subprocess
            import platform
            try:
                param = '-n' if platform.system().lower() == 'windows' else '-c'
                command = ['ping', param, '1', '114.114.114.114']
                result = subprocess.run(command, capture_output=True, timeout=self.timeout)
                return result.returncode == 0
            except Exception:
                return False
        except Exception:
            return False

    async def monitor_connection(self, callback: Callable[[bool], None]):
        """监控连接状态"""
        self.monitoring = True
        self.last_success_time = time.time()

        while self.monitoring:
            try:
                connected = await self.check_connection()

                if connected:
                    self.last_success_time = time.time()
                    self.failures = 0
                else:
                    self.failures += 1
                    log(f"网络连接失败 ({self.failures}/{self.max_failures})")

                    if self.failures >= self.max_failures:
                        log("网络连接持续失败，触发重连")
                        callback(False)
                        self.failures = 0

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log(f"连接监控异常: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False


class BrowserHealthChecker:
    """浏览器健康检查器"""

    def __init__(self, page, check_interval: float = 60.0):
        self.page = page
        self.check_interval = check_interval
        self.checking = False

    async def check_browser_health(self) -> Dict[str, Any]:
        """检查浏览器健康状态"""
        try:
            # 检查页面是否仍然有效
            if self.page.is_closed():
                return {"healthy": False, "reason": "page_closed"}

            # 检查页面是否响应
            try:
                await self.page.evaluate("1+1", timeout=5000)
                return {"healthy": True}
            except Exception as e:
                return {"healthy": False, "reason": f"page_unresponsive: {e}"}

        except Exception as e:
            return {"healthy": False, "reason": f"check_failed: {e}"}

    async def monitor_browser_health(self, callback: Callable[[Dict[str, Any]], None]):
        """监控浏览器健康状态"""
        self.checking = True

        while self.checking:
            try:
                health_status = await self.check_browser_health()

                if not health_status.get("healthy", False):
                    log(f"浏览器健康检查失败: {health_status.get('reason', '未知')}")
                    callback(health_status)

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log(f"浏览器健康监控异常: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_monitoring(self):
        """停止监控"""
        self.checking = False


# 全局自动重连实例
auto_reconnect = AutoReconnect()

# 自动重连装饰器
def auto_reconnect_decorator(max_retries: int = 3):
    """自动重连装饰器（简化版）"""
    return auto_reconnect.reconnect_decorator(max_retries)


async def test_connection(url: str = "https://www.baidu.com", timeout: float = 10.0) -> bool:
    """测试网络连接"""
    try:
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(url) as response:
                return response.status == 200
    except ImportError:
        # 回退方法
        import urllib.request
        import ssl
        try:
            ssl._create_default_https_context = ssl._create_unverified_context
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.getcode() == 200
        except Exception:
            return False
    except Exception:
        return False