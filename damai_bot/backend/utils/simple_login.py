#!/usr/bin/env python3
"""
简化版大麦网登录服务
基于Playwright，不依赖数据库
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Any, List

from backend.anti_detect import get_browser_args, get_random_user_agent, create_stealth_context

logger = logging.getLogger(__name__)


class DamaiLoginSimple:
    """简化版大麦网登录服务"""

    def __init__(self, headless: bool = False):
        self.playwright = None
        self.browser = None
        self.context = None
        self.headless = headless

        # 大麦网配置
        self.DAMAI_BASE_URL = "https://www.damai.cn"
        self.DAMAI_LOGIN_URL = "https://passport.damai.cn/login"

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def init_browser(self):
        """初始化浏览器"""
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=get_browser_args()
            )
            logger.info("浏览器初始化成功")
        except ImportError:
            logger.error("Playwright未安装，请运行: pip install playwright && playwright install")
            raise
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            raise

    async def close(self):
        """关闭资源"""
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

    async def create_context(self, cookies: Optional[List[Dict[str, Any]]] = None):
        """创建浏览器上下文（带反检测措施）"""
        context = await create_stealth_context(self.browser)

        if cookies:
            try:
                await context.add_cookies(cookies)
                logger.info(f"已加载 {len(cookies)} 个Cookie到浏览器上下文")
            except Exception as e:
                logger.error(f"加载Cookie失败: {e}")

        self.context = context
        return context

    async def check_login_status(self, page) -> bool:
        """检查登录状态"""
        try:
            await page.goto(self.DAMAI_BASE_URL, timeout=10000)
            await page.wait_for_load_state('networkidle', timeout=5000)

            # 检查是否有登录相关的元素
            login_elements = await page.query_selector_all('text="退出登录", text="我的大麦"')
            return len(login_elements) > 0
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False

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

    async def get_cookies(self, context) -> List[Dict[str, Any]]:
        """获取当前上下文的Cookie"""
        cookies = await context.cookies()
        return cookies

    async def test_login(self, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """测试登录状态"""
        try:
            context = await self.create_context(cookies)
            page = await context.new_page()

            is_logged_in = await self.check_login_status(page)
            user_info = {}

            if is_logged_in:
                # 尝试获取用户信息
                try:
                    await page.goto(f"{self.DAMAI_BASE_URL}/my", timeout=10000)
                    # 这里可以添加更多用户信息提取逻辑
                    user_info["status"] = "logged_in"
                except Exception as e:
                    logger.error(f"获取用户信息失败: {e}")
                    user_info["status"] = "logged_in_no_info"
            else:
                user_info["status"] = "not_logged_in"

            await context.close()

            return {
                "success": is_logged_in,
                "user_info": user_info,
                "message": "已登录" if is_logged_in else "未登录"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "登录测试失败"
            }

    async def login_with_qrcode(self) -> Optional[List[Dict[str, Any]]]:
        """扫码登录并返回Cookie"""
        try:
            context = await self.create_context()
            page = await context.new_page()

            if await self.manual_qrcode_login(page):
                cookies = await self.get_cookies(context)
                logger.info(f"获取到 {len(cookies)} 个Cookie")
                return cookies
            else:
                logger.error("扫码登录失败")
                return None
        except Exception as e:
            logger.error(f"扫码登录异常: {e}")
            return None
        finally:
            await self.close()


# 同步包装函数
def sync_login_with_qrcode(headless: bool = False) -> Optional[List[Dict[str, Any]]]:
    """同步版本的扫码登录"""
    return asyncio.run(DamaiLoginSimple(headless=headless).login_with_qrcode())

def sync_test_login(cookies: List[Dict[str, Any]], headless: bool = False) -> Dict[str, Any]:
    """同步版本的测试登录"""
    return asyncio.run(DamaiLoginSimple(headless=headless).test_login(cookies))