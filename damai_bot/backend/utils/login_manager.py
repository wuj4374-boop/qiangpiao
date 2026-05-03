#!/usr/bin/env python3
"""
登录管理模块 - 优化版
使用Windows 11 Edge浏览器和Playwright Persistent Context
支持浏览器状态持久化，自动检测登录失效并提示重新登录
"""

import json
import logging
import os
from typing import Dict, Optional, Any, List

# 导入Cookie管理器
try:
    from backend.utils.cookie_manager import cookie_manager
    HAS_COOKIE_MANAGER = True
except ImportError:
    logging.warning("无法导入Cookie管理器")
    HAS_COOKIE_MANAGER = False
    cookie_manager = None

# 导入Edge浏览器登录管理器
try:
    from backend.utils.edge_login import EdgeLoginManager
    HAS_LOGIN_SERVICE = True
except ImportError as e:
    logging.warning(f"无法导入Edge登录管理器: {e}")
    HAS_LOGIN_SERVICE = False
    EdgeLoginManager = None

logger = logging.getLogger(__name__)


class LoginManager:
    """登录管理器"""

    def __init__(self):
        # 配置文件路径
        self.cookie_file = "config/cookies.json"
        self.storage_state_file = "config/edge_storage_state.json"
        self.browser_profile_dir = "config/browser_profile"

        # 确保配置目录存在
        os.makedirs("config", exist_ok=True)
        os.makedirs(self.browser_profile_dir, exist_ok=True)

    async def qrcode_login(self, headless: bool = False) -> Dict[str, Any]:
        """
        扫码登录大麦网

        Args:
            headless: 是否使用无头模式（默认False，显示浏览器）

        Returns:
            Dict[str, Any]: 登录结果
        """
        if not HAS_LOGIN_SERVICE:
            return {
                "success": False,
                "message": "登录服务不可用，缺少依赖",
                "cookies": None
            }

        try:
            # 创建Edge登录管理器实例，使用持久化上下文
            login_manager = EdgeLoginManager(headless=headless, persistent_context=True)
            await login_manager.init_browser()

            # 执行扫码登录
            logger.info("开始扫码登录大麦网...")
            cookies = await login_manager.login_with_qrcode()

            if cookies:
                # 保存Cookie到文件
                if HAS_COOKIE_MANAGER:
                    save_success = cookie_manager.save_cookies(cookies, self.cookie_file)
                    if save_success:
                        logger.info(f"登录成功，Cookie已保存到 {self.cookie_file}")
                    else:
                        logger.warning("登录成功，但Cookie保存失败")

                # 保存storage state（持久化登录状态）
                await login_manager.save_storage_state()

                await login_manager.close()

                return {
                    "success": True,
                    "cookies": cookies,
                    "cookies_count": len(cookies),
                    "message": "扫码登录成功，Cookie和浏览器状态已保存",
                    "cookie_file": self.cookie_file,
                    "browser_profile": self.browser_profile_dir,
                    "storage_state": self.storage_state_file
                }
            else:
                await login_manager.close()
                return {
                    "success": False,
                    "cookies": None,
                    "message": "扫码登录失败，请重试"
                }

        except Exception as e:
            logger.error(f"扫码登录过程中发生错误: {e}")
            return {
                "success": False,
                "cookies": None,
                "message": f"登录过程出错: {str(e)}"
            }

    async def check_login_status(self, cookies: Optional[List[Dict[str, Any]]] = None, headless: bool = True) -> Dict[str, Any]:
        """
        检查登录状态（验证Cookie是否有效）

        Args:
            cookies: 要验证的Cookie列表，如果为None则从文件加载
            headless: 是否使用无头模式验证（默认True，不显示浏览器）

        Returns:
            Dict[str, Any]: 验证结果，包含needs_relogin字段指示是否需要重新登录
        """
        if not HAS_LOGIN_SERVICE:
            return {
                "valid": False,
                "message": "登录服务不可用，无法验证Cookie",
                "user_info": {},
                "needs_relogin": True
            }

        try:
            # 优先使用持久化上下文检查登录状态（浏览器配置文件）
            login_manager = None
            try:
                login_manager = EdgeLoginManager(headless=headless, persistent_context=True)
                await login_manager.init_browser()

                # 测试当前上下文的登录状态
                result = await login_manager.test_login()
                await login_manager.close()
                login_manager = None

                if result.get("success", False):
                    # 持久化上下文登录有效
                    return {
                        "valid": True,
                        "message": "浏览器状态有效，已登录大麦账号",
                        "user_info": result.get("user_info", {}),
                        "needs_relogin": result.get("needs_relogin", False),
                        "details": result,
                        "login_method": "browser_profile"
                    }
                else:
                    # 持久化上下文无效，继续尝试Cookie验证
                    logger.info("浏览器状态无效，尝试使用Cookie验证")
            except Exception as e:
                logger.warning(f"浏览器状态检查失败: {e}")
                if login_manager:
                    await login_manager.close()
                # 继续尝试Cookie验证

        except Exception as e:
            logger.error(f"浏览器状态检查异常: {e}")
            # 继续尝试Cookie验证

        # 如果浏览器状态无效，尝试使用Cookie验证
        # 加载Cookie
        if cookies is None and HAS_COOKIE_MANAGER:
            cookies = cookie_manager.load_cookies(self.cookie_file)

        if not cookies:
            return {
                "valid": False,
                "message": "未找到Cookie且浏览器状态无效，请先登录",
                "user_info": {},
                "needs_relogin": True
            }

        try:
            # 使用Cookie验证登录状态
            login_manager = EdgeLoginManager(headless=headless, persistent_context=False)
            await login_manager.init_browser()
            result = await login_manager.test_login(cookies)
            await login_manager.close()

            needs_relogin = result.get("needs_relogin", True) or not result.get("success", False)

            return {
                "valid": result.get("success", False),
                "message": result.get("message", "验证完成"),
                "user_info": result.get("user_info", {}),
                "needs_relogin": needs_relogin,
                "details": result,
                "login_method": "cookies"
            }

        except Exception as e:
            logger.error(f"验证Cookie时发生错误: {e}")
            return {
                "valid": False,
                "message": f"验证过程出错: {str(e)}",
                "user_info": {},
                "needs_relogin": True
            }

    def get_cookie_info(self) -> Dict[str, Any]:
        """
        获取Cookie文件信息

        Returns:
            Dict[str, Any]: Cookie文件信息
        """
        if not HAS_COOKIE_MANAGER:
            return {
                "exists": False,
                "message": "Cookie管理器不可用",
                "file_path": self.cookie_file
            }

        info = cookie_manager.get_cookie_file_info(self.cookie_file)

        if info:
            return info
        else:
            return {
                "exists": False,
                "message": "Cookie文件不存在或格式错误",
                "file_path": self.cookie_file
            }

    async def refresh_login(self) -> Dict[str, Any]:
        """
        刷新登录（重新扫码登录）

        Returns:
            Dict[str, Any]: 刷新结果
        """
        return await self.qrcode_login(headless=False)

    def delete_cookies(self) -> Dict[str, Any]:
        """
        删除保存的Cookie

        Returns:
            Dict[str, Any]: 删除结果
        """
        if not HAS_COOKIE_MANAGER:
            return {
                "success": False,
                "message": "Cookie管理器不可用"
            }

        success = cookie_manager.delete_cookies(self.cookie_file)

        if success:
            return {
                "success": True,
                "message": "Cookie已删除",
                "file_path": self.cookie_file
            }
        else:
            return {
                "success": False,
                "message": "Cookie删除失败",
                "file_path": self.cookie_file
            }

    async def get_user_info(self) -> Dict[str, Any]:
        """
        获取用户信息（需要有效的Cookie）

        Returns:
            Dict[str, Any]: 用户信息，包含needs_relogin字段指示是否需要重新登录
        """
        status_result = await self.check_login_status(headless=True)

        if status_result["valid"]:
            return {
                "success": True,
                "logged_in": True,
                "user_info": status_result.get("user_info", {}),
                "needs_relogin": status_result.get("needs_relogin", False),
                "message": "已登录大麦账号",
                "login_method": status_result.get("login_method", "unknown")
            }
        else:
            return {
                "success": False,
                "logged_in": False,
                "user_info": {},
                "needs_relogin": status_result.get("needs_relogin", True),
                "message": status_result.get("message", "未登录"),
                "login_method": status_result.get("login_method", "none")
            }


# 创建全局登录管理器实例
login_manager = LoginManager()


# 同步包装函数（用于在非异步环境中调用）
def sync_qrcode_login() -> Dict[str, Any]:
    """同步版本的扫码登录"""
    import asyncio
    return asyncio.run(login_manager.qrcode_login(headless=False))

def sync_check_login_status() -> Dict[str, Any]:
    """同步版本的检查登录状态"""
    import asyncio
    return asyncio.run(login_manager.check_login_status(headless=True))

def sync_refresh_login() -> Dict[str, Any]:
    """同步版本的刷新登录"""
    import asyncio
    return asyncio.run(login_manager.refresh_login())

def sync_get_user_info() -> Dict[str, Any]:
    """同步版本的获取用户信息"""
    import asyncio
    return asyncio.run(login_manager.get_user_info())