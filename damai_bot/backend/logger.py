"""
大麦抢票系统 - 统一日志配置模块

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。

技术要点：
- RotatingFileHandler：日志文件轮转（10MB 上限，保留 5 个备份）
- 双日志文件：run.log（全部 INFO+）和 error.log（仅 WARNING+）
- StreamHandler：控制台输出
- 错误分类标记：[NETWORK] [LOGIN] [CAPTCHA] [STOCK]
- 单例模式：全局只初始化一次根日志记录器

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import os
import logging
import logging.handlers
from typing import Optional

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 日志格式
_FILE_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
_CONSOLE_FORMAT = "[%(asctime)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_CONSOLE_DATE_FORMAT = "%H:%M:%S"

# 全局标记，防止重复初始化
_initialized = False
_root_logger = None


def _setup_root_logger():
    """配置根日志记录器（只执行一次）"""
    global _initialized, _root_logger
    if _initialized:
        return

    _root_logger = logging.getLogger("damai")
    _root_logger.setLevel(logging.DEBUG)

    # 防止日志传递到 Python 根记录器（避免重复输出）
    _root_logger.propagate = False

    # 清除已有 handler（防止重复添加）
    _root_logger.handlers.clear()

    # 1. run.log —— 记录所有 INFO 及以上
    run_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "run.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    run_handler.setLevel(logging.INFO)
    run_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))

    # 2. error.log —— 只记录 WARNING 及以上
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "error.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))

    # 3. 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT, datefmt=_CONSOLE_DATE_FORMAT))

    _root_logger.addHandler(run_handler)
    _root_logger.addHandler(error_handler)
    _root_logger.addHandler(console_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    获取子日志记录器，所有模块统一使用

    用法：
        from backend.logger import get_logger
        logger = get_logger(__name__)
        logger.info("xxx")
        logger.error("[NETWORK] 连接超时")
    """
    _setup_root_logger()
    return _root_logger.getChild(name)


# ── 错误分类便捷函数 ──

def log_network_error(logger: logging.Logger, message: str, *args, **kwargs):
    """记录网络错误，标记 [NETWORK]"""
    logger.error("[NETWORK] " + message, *args, **kwargs)


def log_login_error(logger: logging.Logger, message: str, *args, **kwargs):
    """记录登录失效错误，标记 [LOGIN]"""
    logger.error("[LOGIN] " + message, *args, **kwargs)


def log_captcha_error(logger: logging.Logger, message: str, *args, **kwargs):
    """记录验证码错误，标记 [CAPTCHA]"""
    logger.error("[CAPTCHA] " + message, *args, **kwargs)


def log_stock_error(logger: logging.Logger, message: str, *args, **kwargs):
    """记录库存不足错误，标记 [STOCK]"""
    logger.error("[STOCK] " + message, *args, **kwargs)


# ── 兼容旧代码的便捷 log 函数 ──

_compat_logger = get_logger("compat")


def log(message: str):
    """
    兼容旧代码的 log() 函数
    直接调用 _compat_logger.info()
    """
    _compat_logger.info(message)
