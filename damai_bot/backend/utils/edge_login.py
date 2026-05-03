#!/usr/bin/env python3
"""
Edge浏览器登录模块 - 优化版
使用Windows 11自带Edge浏览器，通过Playwright调用
使用Persistent Context保存浏览器登录状态，避免重复扫码
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from backend.anti_detect import get_browser_args, get_random_user_agent, apply_stealth_to_context

logger = logging.getLogger(__name__)


class EdgeLoginManager:
    """Edge浏览器登录管理器"""

    def __init__(self, headless: bool = False, persistent_context: bool = True):
        """
        初始化Edge登录管理器

        Args:
            headless: 是否使用无头模式
            persistent_context: 是否使用持久化上下文保存登录状态
        """
        self.playwright = None
        self.browser = None
        self.context = None
        self.headless = headless
        self.persistent_context = persistent_context

        # 配置文件路径
        self.cookie_file = "config/cookies.json"
        self.storage_state_file = "config/edge_storage_state.json"
        self.context_dir = "config/browser_profile"  # 使用用户指定的路径

        # 大麦网配置
        self.DAMAI_BASE_URL = "https://www.damai.cn"
        self.DAMAI_LOGIN_URL = "https://passport.damai.cn/login"

        # 确保配置目录存在
        os.makedirs("config", exist_ok=True)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def init_browser(self):
        """初始化Edge浏览器和上下文（带反检测措施）"""
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()

            # 确保上下文目录存在
            os.makedirs(self.context_dir, exist_ok=True)

            # 统一的反检测启动参数
            anti_detect_args = get_browser_args(["--start-maximized"])
            random_ua = get_random_user_agent()

            if self.persistent_context:
                # 使用持久化上下文（自动保存登录状态）
                try:
                    self.context = await self.playwright.chromium.launch_persistent_context(
                        self.context_dir,
                        channel="msedge",
                        headless=self.headless,
                        viewport={'width': 1440, 'height': 900},
                        user_agent=random_ua,
                        args=anti_detect_args,
                        ignore_https_errors=True
                    )
                    logger.info("Edge浏览器持久化上下文启动成功（使用channel模式）")
                except Exception as e:
                    logger.warning(f"channel模式持久化上下文启动失败，尝试使用executable_path: {e}")
                    # 方法2：使用executable_path指定Edge路径
                    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                    if os.path.exists(edge_path):
                        self.context = await self.playwright.chromium.launch_persistent_context(
                            self.context_dir,
                            executable_path=edge_path,
                            headless=self.headless,
                            viewport={'width': 1440, 'height': 900},
                            user_agent=random_ua,
                            args=anti_detect_args,
                            ignore_https_errors=True
                        )
                        logger.info("Edge浏览器持久化上下文启动成功（使用executable_path）")
                    else:
                        # 方法3：使用默认Chromium（fallback）
                        logger.warning("未找到Edge浏览器，使用Chromium作为后备")
                        self.context = await self.playwright.chromium.launch_persistent_context(
                            self.context_dir,
                            headless=self.headless,
                            viewport={'width': 1440, 'height': 900},
                            user_agent=random_ua,
                            args=anti_detect_args,
                            ignore_https_errors=True
                        )
                        logger.info("Chromium浏览器持久化上下文启动成功（后备方案）")

                # 注入反检测 JS 脚本
                await apply_stealth_to_context(self.context)

                # 从持久化上下文中获取browser对象
                self.browser = self.context.browser

                # 检查现有Cookie
                cookies = await self.context.cookies()
                if cookies:
                    logger.info(f"持久化上下文已包含 {len(cookies)} 个Cookie")

            else:
                # 使用普通浏览器上下文
                # 启动Edge浏览器（使用Windows 11自带Edge）
                # 方法1：使用channel参数（推荐）
                try:
                    self.browser = await self.playwright.chromium.launch(
                        channel="msedge",
                        headless=self.headless,
                        args=anti_detect_args
                    )
                    logger.info("Edge浏览器启动成功（使用channel模式）")
                except Exception as e:
                    logger.warning(f"channel模式启动失败，尝试使用executable_path: {e}")
                    # 方法2：使用executable_path指定Edge路径
                    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                    if os.path.exists(edge_path):
                        self.browser = await self.playwright.chromium.launch(
                            executable_path=edge_path,
                            headless=self.headless,
                            args=anti_detect_args
                        )
                        logger.info("Edge浏览器启动成功（使用executable_path）")
                    else:
                        # 方法3：使用默认Chromium（fallback）
                        logger.warning("未找到Edge浏览器，使用Chromium作为后备")
                        self.browser = await self.playwright.chromium.launch(
                            headless=self.headless,
                            args=anti_detect_args
                        )
                        logger.info("Chromium浏览器启动成功（后备方案）")

                # 创建普通浏览器上下文（带反检测措施）
                self.context = await self.browser.new_context(
                    viewport={'width': 1440, 'height': 900},
                    user_agent=random_ua,
                    ignore_https_errors=True
                )
                await apply_stealth_to_context(self.context)
                logger.info("普通浏览器上下文创建成功（已注入反检测脚本）")

        except ImportError:
            logger.error("Playwright未安装，请运行: pip install playwright && playwright install")
            raise
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            raise


    async def save_storage_state(self):
        """保存浏览器storage state（包括Cookie、localStorage等）"""
        if not self.context:
            logger.warning("没有活动的浏览器上下文，无法保存storage state")
            return False

        try:
            storage_state = await self.context.storage_state()
            with open(self.storage_state_file, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, ensure_ascii=False, indent=2)
            logger.info(f"Storage state已保存到: {self.storage_state_file}")
            return True
        except Exception as e:
            logger.error(f"保存storage state失败: {e}")
            return False

    async def save_cookies(self, cookies: List[Dict[str, Any]] = None):
        """
        保存Cookie到文件

        Args:
            cookies: Cookie列表，如果为None则从当前上下文获取
        """
        try:
            if cookies is None and self.context:
                cookies = await self.context.cookies()

            if not cookies:
                logger.warning("没有Cookie可保存")
                return False

            # 确保目录存在
            os.makedirs(os.path.dirname(self.cookie_file), exist_ok=True)

            # 添加保存时间戳
            cookie_data = {
                "saved_at": datetime.now().isoformat(),
                "browser": "edge",
                "cookies": cookies
            }

            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Cookie已保存到 {self.cookie_file}, 共 {len(cookies)} 个cookie")
            return True

        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
            return False

    async def check_login_status(self, page) -> Dict[str, Any]:
        """检查登录状态，返回详细状态信息

        Returns:
            Dict包含:
            - logged_in: bool 是否已登录
            - status: str 状态描述
            - reason: str 如果未登录，原因描述
            - needs_relogin: bool 是否需要重新登录（登录失效）
        """
        try:
            await page.goto(self.DAMAI_BASE_URL, timeout=15000)
            await page.wait_for_load_state('networkidle', timeout=8000)

            # 检查是否有"退出登录"按钮
            logout_button = await page.query_selector('text="退出登录"')
            # 检查是否有"我的大麦"链接
            my_damai_link = await page.query_selector('text="我的大麦"')

            if logout_button or my_damai_link:
                # 已登录状态
                return {
                    "logged_in": True,
                    "status": "已登录",
                    "reason": "",
                    "needs_relogin": False
                }
            else:
                # 检查是否有登录相关元素（如"登录"按钮）
                login_button = await page.query_selector('text="登录"')
                if login_button:
                    # 未登录状态
                    return {
                        "logged_in": False,
                        "status": "未登录",
                        "reason": "检测到登录按钮，用户未登录",
                        "needs_relogin": True
                    }
                else:
                    # 无法确定状态，可能是页面加载异常
                    return {
                        "logged_in": False,
                        "status": "未知",
                        "reason": "无法检测登录状态，页面可能异常",
                        "needs_relogin": True
                    }
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return {
                "logged_in": False,
                "status": "错误",
                "reason": f"检查登录状态时发生异常: {str(e)}",
                "needs_relogin": True
            }

    async def manual_qrcode_login(self, page) -> bool:
        """手动扫码登录"""
        try:
            logger.info("正在打开大麦登录页面...")
            await page.goto(self.DAMAI_LOGIN_URL, timeout=30000)
            await page.wait_for_load_state('networkidle', timeout=10000)

            # 等待二维码出现
            qr_code_selector = '.login-qrcode, .qrcode-img, [class*="qrcode"]'
            await page.wait_for_selector(qr_code_selector, timeout=10000)

            logger.info("二维码已出现，请使用大麦APP扫码登录...")
            print("=" * 50)
            print("请使用大麦APP扫描浏览器中的二维码进行登录")
            print("登录成功后窗口会自动关闭")
            print("=" * 50)

            # 等待登录成功（检查是否有退出登录按钮）
            await page.wait_for_selector('text="退出登录"', timeout=120000)

            logger.info("扫码登录成功！")
            return True
        except Exception as e:
            logger.error(f"扫码登录失败: {e}")
            return False

    async def login_with_qrcode(self) -> Optional[List[Dict[str, Any]]]:
        """
        扫码登录并返回Cookie

        Returns:
            Cookie列表，登录失败返回None
        """
        try:
            # 创建新页面
            page = await self.context.new_page()

            # 执行扫码登录
            if await self.manual_qrcode_login(page):
                # 获取Cookie
                cookies = await self.context.cookies()
                logger.info(f"获取到 {len(cookies)} 个Cookie")

                # 保存Cookie到文件
                await self.save_cookies(cookies)

                # 保存storage state（持久化登录状态）
                if self.persistent_context:
                    await self.save_storage_state()

                # 关闭页面（保持浏览器打开）
                await page.close()

                return cookies
            else:
                logger.error("扫码登录失败")
                return None

        except Exception as e:
            logger.error(f"扫码登录异常: {e}")
            return None

    async def test_login(self, cookies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        测试登录状态

        Args:
            cookies: 要测试的Cookie列表，如果为None则使用当前上下文

        Returns:
            测试结果字典
        """
        try:
            # 如果提供了Cookie，创建临时上下文
            if cookies and not self.context:
                await self.init_browser()

            page = await self.context.new_page()

            status_result = await self.check_login_status(page)
            is_logged_in = status_result.get("logged_in", False)
            needs_relogin = status_result.get("needs_relogin", True)
            user_info = {
                "status": status_result.get("status", "未知"),
                "reason": status_result.get("reason", ""),
                "needs_relogin": needs_relogin
            }

            if is_logged_in:
                # 尝试获取更多用户信息
                try:
                    await page.goto(f"{self.DAMAI_BASE_URL}/my", timeout=10000)
                    # 这里可以添加更多用户信息提取逻辑
                    user_info["detail"] = "logged_in"
                except Exception as e:
                    logger.error(f"获取用户信息失败: {e}")
                    user_info["detail"] = "logged_in_no_info"
            else:
                user_info["detail"] = "not_logged_in"

            await page.close()

            return {
                "success": is_logged_in,
                "user_info": user_info,
                "message": status_result.get("status", "未知状态"),
                "needs_relogin": needs_relogin,
                "status_detail": status_result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "登录测试失败",
                "needs_relogin": True,
                "user_info": {
                    "status": "错误",
                    "reason": f"测试异常: {str(e)}"
                }
            }

    async def close(self):
        """关闭浏览器资源"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("浏览器资源已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器资源时出错: {e}")


# 同步包装函数
def sync_login_with_qrcode(headless: bool = False) -> Optional[List[Dict[str, Any]]]:
    """同步版本的扫码登录"""
    async def _login():
        async with EdgeLoginManager(headless=headless) as login_manager:
            return await login_manager.login_with_qrcode()

    return asyncio.run(_login())

def sync_test_login(cookies: List[Dict[str, Any]] = None, headless: bool = True) -> Dict[str, Any]:
    """同步版本的测试登录"""
    async def _test():
        async with EdgeLoginManager(headless=headless) as login_manager:
            return await login_manager.test_login(cookies)

    return asyncio.run(_test())

def sync_save_storage_state(headless: bool = True) -> bool:
    """同步版本的保存storage state"""
    async def _save():
        async with EdgeLoginManager(headless=headless) as login_manager:
            return await login_manager.save_storage_state()

    return asyncio.run(_save())


# 主函数 - 测试登录
async def main():
    """主测试函数"""
    print("=" * 50)
    print("Edge浏览器登录模块测试")
    print("=" * 50)

    # 创建登录管理器
    login_manager = EdgeLoginManager(headless=False, persistent_context=True)

    try:
        await login_manager.init_browser()

        # 检查是否已有登录状态
        print("检查现有登录状态...")
        test_result = await login_manager.test_login()
        if test_result.get("success"):
            print("✓ 已有有效的登录状态，无需重新登录")
            print(f"  用户状态: {test_result.get('user_info', {}).get('status', '未知')}")

            # 获取并显示Cookie信息
            cookies = await login_manager.context.cookies()
            print(f"  当前上下文包含 {len(cookies)} 个Cookie")

            # 保存Cookie到文件
            await login_manager.save_cookies()

        else:
            print("✗ 未检测到有效登录状态，开始扫码登录...")

            # 执行扫码登录
            cookies = await login_manager.login_with_qrcode()
            if cookies:
                print(f"✓ 登录成功，获取到 {len(cookies)} 个Cookie")
                print(f"  Cookie已保存到: {login_manager.cookie_file}")
                print(f"  Storage state已保存到: {login_manager.storage_state_file}")
            else:
                print("✗ 登录失败")

    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
    finally:
        await login_manager.close()

    print("=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 运行主函数
    asyncio.run(main())