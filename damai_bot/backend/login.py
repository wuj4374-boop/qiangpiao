"""
大麦抢票系统 - 登录管理模块

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。

技术要点：
- Cookie 持久化存储与加载
- 扫码登录流程（Playwright 自动打开登录页）
- 登录状态自动检测与刷新
- LoginManager 自动保持登录状态

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import asyncio
import json
import os
from typing import Dict

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

try:
    from .utils import load_json, save_json, log
except ImportError:
    from utils import load_json, save_json, log

try:
    from backend.anti_detect import create_stealth_context, apply_stealth_to_context, get_random_user_agent
except ImportError:
    try:
        from .anti_detect import create_stealth_context, apply_stealth_to_context, get_random_user_agent
    except ImportError:
        create_stealth_context = None
        apply_stealth_to_context = None
        get_random_user_agent = None

COOKIE_PATH = os.path.join(os.path.dirname(__file__), 'cookies.json')


def get_cookie_file_path():
    return COOKIE_PATH


async def load_cookies(context: BrowserContext, cookie_path: str = None):
    if cookie_path is None:
        cookie_path = get_cookie_file_path()
    if not os.path.exists(cookie_path):
        return False
    cookies = load_json(cookie_path)
    if not cookies:
        return False
    await context.add_cookies(cookies)
    log('已加载本地 Cookie。')
    return True


async def save_cookies(context: BrowserContext, cookie_path: str = None):
    if cookie_path is None:
        cookie_path = get_cookie_file_path()
    cookies = await context.cookies()
    save_json(cookie_path, cookies)
    log(f'已保存 Cookie 到 {cookie_path}')


async def manual_login(page: Page, concert_name: str = ''):
    log('开始手动扫码登录流程(请在页面扫码登录)...')
    await page.goto('https://passport.damai.cn/login')
    # 等待页面加载
    await page.wait_for_load_state('networkidle', timeout=30000)
    log('登录页面加载完成，请扫码...')
    # 等待登录
    await page.wait_for_selector('text="退出登录"', timeout=120000)
    log('扫描成功，登录状态已建立。')


async def is_logged_in(page: Page) -> bool:
    try:
        await page.reload()
        await page.wait_for_selector('text="退出登录"', timeout=5000)
        return True
    except Exception:
        return False


async def ensure_logged_in(browser: Browser, concert_name: str = '') -> BrowserContext:
    if create_stealth_context:
        context = await create_stealth_context(browser)
    else:
        context = await browser.new_context(viewport={'width': 1440, 'height': 900})
    cookie_loaded = await load_cookies(context)

    page = await context.new_page()
    await page.goto('https://www.damai.cn')

    if cookie_loaded:
        if await is_logged_in(page):
            log('Cookie 登录验证成功。')
            return context
        else:
            log('Cookie 无效，需要扫码登录。')

    await manual_login(page, concert_name)
    await save_cookies(context)
    return context


async def create_browser_context():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False, args=[
        '--disable-gpu',
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--disable-extensions',
        '--disable-background-networking',
    ])
    context = await ensure_logged_in(browser)
    # 拦截图片请求以降低内存消耗
    async def block_images(route):
        if route.request.resource_type == 'image':
            await route.abort()
        else:
            await route.continue_()
    await context.route('**/*', block_images)
    return playwright, browser, context


class LoginManager:
    """登录管理器（自动登录保持）"""

    def __init__(self, browser, concert_name: str = ''):
        self.browser = browser
        self.concert_name = concert_name
        self.context = None
        self.refresh_interval = 300  # 5分钟
        self.refresh_task = None
        self.running = False

    async def start(self):
        """启动登录管理器"""
        if self.running:
            return

        self.running = True
        self.context = await ensure_logged_in(self.browser, self.concert_name)

        # 启动自动刷新任务
        self.refresh_task = asyncio.create_task(self._auto_refresh_loop())

        log("登录管理器已启动")

    async def stop(self):
        """停止登录管理器"""
        self.running = False
        if self.refresh_task:
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
            self.refresh_task = None

        if self.context:
            await self.context.close()
            self.context = None

        log("登录管理器已停止")

    async def _auto_refresh_loop(self):
        """自动刷新循环"""
        while self.running:
            try:
                await asyncio.sleep(self.refresh_interval)

                if not self.running:
                    break

                log("开始自动登录状态检查...")

                # 检查登录状态
                if not await self._check_login_status():
                    log("登录状态失效，尝试重新登录...")
                    await self._re_login()

            except asyncio.CancelledError:
                break
            except Exception as e:
                log(f"自动登录检查异常: {e}")
                await asyncio.sleep(60)  # 异常后等待1分钟

    async def _check_login_status(self) -> bool:
        """检查登录状态"""
        if not self.context:
            return False

        try:
            # 创建新页面检查登录状态
            page = await self.context.new_page()
            await page.goto('https://www.damai.cn', timeout=30000)

            # 检查是否显示"退出登录"按钮
            try:
                await page.wait_for_selector('text="退出登录"', timeout=5000)
                logged_in = True
            except Exception:
                logged_in = False

            await page.close()
            return logged_in

        except Exception as e:
            log(f"检查登录状态失败: {e}")
            return False

    async def _re_login(self):
        """重新登录"""
        try:
            # 关闭旧上下文
            if self.context:
                await self.context.close()

            # 创建新上下文并重新登录
            self.context = await ensure_logged_in(self.browser, self.concert_name)
            log("重新登录成功")

        except Exception as e:
            log(f"重新登录失败: {e}")

    def get_context(self):
        """获取浏览器上下文"""
        return self.context


async def ensure_logged_in_with_refresh(browser, concert_name: str = '', refresh_interval: int = 300):
    """确保登录状态（带自动刷新）"""
    manager = LoginManager(browser, concert_name)
    await manager.start()
    return manager


async def check_and_refresh_login(context, max_retries: int = 3) -> bool:
    """检查并刷新登录状态"""
    for attempt in range(max_retries):
        try:
            page = await context.new_page()
            await page.goto('https://www.damai.cn', timeout=30000)

            # 检查登录状态
            try:
                await page.wait_for_selector('text="退出登录"', timeout=5000)
                logged_in = True
            except Exception:
                logged_in = False

            await page.close()

            if logged_in:
                log("登录状态正常")
                return True
            else:
                log("登录状态失效，尝试重新登录...")
                # 这里可以调用重新登录逻辑
                # 简化处理：返回False，由调用者处理
                return False

        except Exception as e:
            log(f"检查登录状态失败（尝试 {attempt + 1}/{max_retries}）: {e}")
            await asyncio.sleep(1)

    return False
