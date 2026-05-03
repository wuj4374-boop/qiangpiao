"""
大麦抢票系统 - 核心抢票引擎

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。
请勿用于任何商业或非法用途。使用前请阅读项目根目录下的 DISCLAIMER.md。

技术要点：
- Playwright 浏览器自动化（页面导航、元素操作、Cookie 管理）
- 移动端 H5 页面适配（m.damai.cn）
- 验证码自动检测与处理
- 观演人自动选择
- 订单自动提交
- 反检测延迟策略

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import asyncio
import datetime
import json
import os
import random
import re
import sys
import time
import platform
from typing import Dict, List

if sys.version_info < (3, 8):
    raise RuntimeError(
        f"当前 Python 版本 {platform.python_version()} 不支持 playwright。请使用 Python 3.8 及以上。"
    )

try:
    from playwright.async_api import BrowserContext, Page  # type: ignore[import]
except ImportError as e:
    raise ImportError(
        "无法导入 playwright.async_api，请先安装 playwright：\n"
        "pip install playwright\n"
        "python -m playwright install\n"
        "或使用 Python 3.8+ 的虚拟环境。"
    ) from e

try:
    from backend.utils import beep_success, log, notify, retry_async, safe_sleep, notify_success, play_sound
    from backend.logger import get_logger, log_network_error, log_login_error, log_captcha_error, log_stock_error
    from backend.notify import notify_success as notify_success_v2
    from backend.features.auto_reconnect import auto_reconnect_decorator
    from backend.features.screenshot import capture_success_screenshot
    from backend.anti_detect import random_click_delay, random_navigation_delay
    from backend.captcha_solver import solve_captcha, solve_slider, detect_captcha_type
except ImportError:
    try:
        from .utils import beep_success, log, notify, retry_async, safe_sleep, notify_success, play_sound
        from .logger import get_logger, log_network_error, log_login_error, log_captcha_error, log_stock_error
        from .notify import notify_success as notify_success_v2
        from .features.auto_reconnect import auto_reconnect_decorator
        from .features.screenshot import capture_success_screenshot
        from .anti_detect import random_click_delay, random_navigation_delay
        from .captcha_solver import solve_captcha, solve_slider, detect_captcha_type
    except ImportError:
        import sys
        import os
        # 添加当前目录到sys.path以确保可以导入utils
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from utils import beep_success, log, notify, retry_async, safe_sleep, notify_success, play_sound
        # 尝试导入统一日志和通知
        try:
            from logger import get_logger, log_network_error, log_login_error, log_captcha_error, log_stock_error
            from notify import notify_success as notify_success_v2
        except ImportError:
            get_logger = lambda name: None
            log_network_error = log_login_error = log_captcha_error = log_stock_error = lambda *a, **kw: None
            notify_success_v2 = notify_success
        # 尝试导入 features
        try:
            from features.auto_reconnect import auto_reconnect_decorator
            from features.screenshot import capture_success_screenshot
        except ImportError:
            # 如果 features 模块不存在，提供空实现
            auto_reconnect_decorator = lambda *args, **kwargs: lambda f: f
            capture_success_screenshot = lambda *args, **kwargs: None
        try:
            from anti_detect import random_click_delay, random_navigation_delay
        except ImportError:
            random_click_delay = lambda: asyncio.sleep(random.uniform(0.05, 0.20))
            random_navigation_delay = lambda: asyncio.sleep(random.uniform(0.5, 1.5))
        # 尝试导入验证码模块
        try:
            from captcha_solver import solve_captcha, solve_slider, detect_captcha_type
        except ImportError:
            solve_captcha = lambda page, *a, **kw: asyncio.sleep(0)
            solve_slider = lambda page, *a, **kw: asyncio.sleep(0)
            detect_captcha_type = lambda page: None

# 获取模块级日志记录器
logger = get_logger("抢票")


def get_mobile_detail_url(event_id: str) -> str:
    """返回移动端详情页 URL"""
    return f'https://m.damai.cn/shows/item.html?id={event_id}'


async def create_mobile_context(playwright):
    """
    创建移动端浏览器上下文（iPhone H5 模拟）
    """
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context(
        viewport={'width': 375, 'height': 812},
        user_agent=(
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) '
            'Version/17.0 Mobile/15E148 Safari/604.1'
        ),
        is_mobile=True,
        has_touch=True,
        locale='zh-CN',
    )
    # 注入反检测脚本
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        window.chrome = {runtime: {}};
    """)
    log('已创建移动端浏览器上下文 (iPhone 375x812)')
    return context


async def handle_captcha(page: Page):
    """检测并处理验证码"""
    try:
        captcha_type = await detect_captcha_type(page)
        if captcha_type:
            log(f'检测到验证码类型: {captcha_type}')
            if captcha_type == 'slider':
                await solve_slider(page)
            else:
                await solve_captcha(page)
            log('验证码处理完成')
            return True
    except Exception as e:
        log(f'验证码处理异常: {e}')
    return False


async def find_concert_page(page: Page, concert_name: str, city: str, date: str):
    query = concert_name.strip()
    log(f"搜索演出: {query} 城市: {city} 日期: {date}")
    await page.goto(f'https://search.damai.cn/search.htm?keyword={query}', timeout=60000)
    await safe_sleep(0.5)
    await random_navigation_delay()

    # 选择演出结果，部分页面需要根据实际 DOM 调整。
    event_selector = 'ul.event-list li a'
    try:
        await page.wait_for_selector(event_selector, timeout=10000)
        elements = await page.query_selector_all(event_selector)
        for item in elements:
            text = (await item.inner_text()).replace('\n', ' ').strip()
            if concert_name in text and city in text:
                link = await item.get_attribute('href')
                if link:
                    url = link if link.startswith('http') else f'https://search.damai.cn{link}'
                    log(f'选择演出页面: {text}')
                    await page.goto(url, timeout=60000)
                    await random_navigation_delay()
                    return True
    except Exception as e:
        log(f'查找演出失败: {e}')

    # 如果找不到则直接访问主站URL
    log('未找到匹配项目，继续在当前页尝试。')
    return False


async def dismiss_mobile_popup(page: Page):
    """关闭大麦网弹出的"移步手机端"提示框"""
    dismiss_selectors = [
        'div.buy-link',
        'text="不，立即购票"',
        'text="不，立即预订"',
        'text="不，选座购票"',
        'text="不，立即抢票"',
    ]
    for sel in dismiss_selectors:
        try:
            btn = await page.query_selector(sel)
            if btn:
                await random_click_delay()
                await btn.click()
                log(f'已关闭手机端提示弹窗')
                await safe_sleep(0.5)
                return True
        except Exception:
            pass
    return False


async def select_session_and_price(page: Page, target_session, price_target, session_id=None, ticket_id=None):
    """
    选择场次和票价
    target_session: str 或 list of str
    price_target: float 或 list of float
    session_id: str, 场次ID（通过data-id属性匹配）
    ticket_id: str, 票档ID（通过data-id属性匹配）
    """
    log(f'尝试选择场次{target_session} 票价{price_target}')

    # 标准化为列表
    if isinstance(target_session, str):
        target_session = [target_session]
    if isinstance(price_target, (int, float)):
        price_target = [float(price_target)]

    await safe_sleep(0.3)

    try:
        # 场次选择（移动端 m.damai.cn + PC 端 fallback）
        session_buttons = await page.query_selector_all(
            'div.perform-info__order div[class*="item"], '
            'div.perform__order__select__performs div.select_right_list_item, '
            'div.show-time-list button, div.show-time-list a'
        )
        selected_session = False

        # 优先通过 session_id 匹配（data-id 属性）
        if session_id and session_buttons:
            for b in session_buttons:
                elem_id = await b.get_attribute('data-id') or await b.get_attribute('data-value') or ''
                if elem_id == session_id:
                    await random_click_delay()
                    await b.click()
                    text = (await b.inner_text()).strip()
                    log(f'已选场次（ID匹配）：{text}')
                    selected_session = True
                    break

        # 降级：通过文本匹配
        if not selected_session:
            for b in session_buttons:
                text = (await b.inner_text()).strip()
                for session in target_session:
                    if session in text:
                        await random_click_delay()
                        await b.click()
                        log(f'已选场次：{text}')
                        selected_session = True
                        break
                if selected_session:
                    break

        await safe_sleep(0.2)

        # 票价选择（移动端 m.damai.cn + PC 端 fallback）
        price_buttons = await page.query_selector_all(
            'div.sku-list div[class*="item"], '
            'div.select_right_list_item.sku_item, '
            'div.price-list button, div.price-list a'
        )

        # 优先通过 ticket_id 匹配（data-id 属性）
        if ticket_id and price_buttons:
            for b in price_buttons:
                elem_id = await b.get_attribute('data-id') or await b.get_attribute('data-value') or ''
                if elem_id == ticket_id:
                    await random_click_delay()
                    await b.click()
                    text = (await b.inner_text()).strip()
                    log(f'已选票价（ID匹配）：{text}')
                    return True

        # 降级：通过文本匹配
        for b in price_buttons:
            text = (await b.inner_text()).strip()
            clean_text = float(re.findall(r"\d+\.?\d*", text)[0]) if re.findall(r"\d+\.?\d*", text) else 0
            for price in price_target:
                if abs(clean_text - price) < 1e-6:
                    await random_click_delay()
                    await b.click()
                    log(f'已选票价：{text}')
                    return True
    except Exception as e:
        log(f'选择场次/票价异常: {e}')
    return False


async def select_viewers(page: Page, viewers: list) -> bool:
    """
    在订单确认页自动选择观演人

    Args:
        page: 页面对象（已停留在订单确认页）
        viewers: 观演人列表，每项包含 name/id_card/phone

    Returns:
        bool: 是否成功选择观演人
    """
    if not viewers:
        return False

    try:
        log(f'尝试选择 {len(viewers)} 位观演人...')

        # 等待观演人区域加载
        await safe_sleep(0.3)

        # 策略1：勾选已保存的观演人（复选框匹配姓名）
        viewer_items = await page.query_selector_all(
            'div.viewer-item, div.passenger-item, div.viewer-list > div, '
            'div.passenger-list > div, div[class*="viewer"], div[class*="passenger"]'
        )

        if viewer_items:
            selected_count = 0
            for item in viewer_items:
                # 获取该条目的姓名文本
                name_el = await item.query_selector(
                    '.viewer-name, .passenger-name, .name, '
                    'span[class*="name"], label[class*="name"]'
                )
                if not name_el:
                    # 尝试从整个条目提取文本
                    item_text = (await item.inner_text()).strip()
                else:
                    item_text = (await name_el.inner_text()).strip()

                # 与配置中的观演人匹配
                for viewer in viewers:
                    viewer_name = viewer.get('name', '')
                    if viewer_name and viewer_name in item_text:
                        # 找到匹配，勾选复选框
                        checkbox = await item.query_selector(
                            'input[type="checkbox"], .viewer-checkbox, '
                            'div[class*="checkbox"], label[class*="checkbox"]'
                        )
                        if checkbox:
                            is_checked = await checkbox.get_attribute('checked')
                            if not is_checked:
                                await random_click_delay()
                                await checkbox.click()
                                log(f'已勾选观演人: {viewer_name}')
                            else:
                                log(f'观演人已勾选: {viewer_name}')
                            selected_count += 1
                        break

            if selected_count > 0:
                log(f'成功选择 {selected_count} 位观演人')
                return True

        # 策略2：尝试点击"新增观演人"按钮并填写信息
        log('未找到已保存的观演人，尝试新增...')
        add_btn = await page.query_selector(
            'button:has-text("新增观演人"), a:has-text("新增观演人"), '
            'div:has-text("新增观演人"), span:has-text("新增观演人"), '
            'button:has-text("添加观演人"), a:has-text("添加观演人")'
        )
        if add_btn:
            for viewer in viewers:
                await random_click_delay()
                await add_btn.click()
                await safe_sleep(0.3)

                # 填写姓名
                name_input = await page.query_selector(
                    'input[placeholder*="姓名"], input[placeholder*="名字"], '
                    'input[name*="name"], input[id*="name"]'
                )
                if name_input:
                    await name_input.fill(viewer.get('name', ''))

                # 填写身份证号
                id_input = await page.query_selector(
                    'input[placeholder*="身份证"], input[placeholder*="证件"], '
                    'input[name*="id"], input[name*="card"], input[id*="id"]'
                )
                if id_input:
                    await id_input.fill(viewer.get('id_card', ''))

                # 填写手机号
                phone_input = await page.query_selector(
                    'input[placeholder*="手机"], input[placeholder*="电话"], '
                    'input[name*="phone"], input[id*="phone"]'
                )
                if phone_input:
                    await phone_input.fill(viewer.get('phone', ''))

                # 点击保存/确认
                save_btn = await page.query_selector(
                    'button:has-text("保存"), button:has-text("确定"), '
                    'button:has-text("确认")'
                )
                if save_btn:
                    await save_btn.click()
                    await safe_sleep(0.3)

                log(f'已新增观演人: {viewer.get("name", "")}')
            return True

        log('未找到观演人选择区域或新增按钮')
        return False

    except Exception as e:
        log(f'选择观演人异常（降级为手动选择）: {e}')
        return False


async def submit_order(page: Page, ticket_count: int = 1, viewers: list = None):
    try:
        log('尝试提交订单...')

        # 先关闭可能存在的手机端弹窗（同时触发购买流程）
        dismissed = await dismiss_mobile_popup(page)
        if dismissed:
            # 关闭弹窗后会跳转到登录页，等待跳转
            await safe_sleep(1)
            # 检查是否跳转到了登录页
            current_url = page.url
            if 'passport.damai.cn/login' in current_url or 'login' in current_url:
                log('已跳转到登录页，请在浏览器中完成登录...')
                # 等待登录完成（用户手动扫码或cookie自动登录）
                try:
                    await page.wait_for_url('**/buy**', timeout=120000)
                    log('登录完成，已进入购买页面')
                    await safe_sleep(1)
                except Exception:
                    # 可能URL格式不同，等待页面变化
                    await safe_sleep(3)
                    log(f'当前页面: {page.url}')

        # 购买按钮选择器（移动端 H5 + PC 端 fallback）
        buy_selectors = [
            'button:has-text("立即抢票")',
            'button:has-text("立即购买")',
            'button:has-text("立即预订")',
            'button:has-text("选座购买")',
            'a:has-text("立即抢票")',
            'a:has-text("立即购买")',
            'a:has-text("立即预订")',
        ]
        buy_btn = None
        for sel in buy_selectors:
            buy_btn = await page.query_selector(sel)
            if buy_btn:
                break

        if buy_btn:
            await random_click_delay()
            await buy_btn.click()
            await safe_sleep(0.5)

        # 点击后检测验证码
        await handle_captcha(page)

        # 订单确认页，选择票数
        if ticket_count > 1:
            try:
                qty = await page.query_selector(
                    'select.ticket-count, input.ticket-count, '
                    'input[class*="num"], input[class*="quantity"]'
                )
                if qty:
                    await qty.fill(str(ticket_count))
            except Exception:
                pass

        # 选择观演人
        if viewers:
            try:
                await select_viewers(page, viewers)
            except Exception as e:
                log(f'观演人选择失败，继续提交: {e}')

        # 提交订单按钮（移动端 H5 + PC 端 fallback）
        confirm_selectors = [
            'button:has-text("提交订单")',
            'button:has-text("确认")',
            'text="立即提交"',
            'span:text("立即提交")',
            'button:has-text("确认购买")',
            'button:has-text("去结算")',
            'button:has-text("确认订单")',
            'button:has-text("立即支付")',
        ]
        confirm_button = None
        for sel in confirm_selectors:
            confirm_button = await page.query_selector(sel)
            if confirm_button:
                break

        if confirm_button:
            await random_click_delay()
            await confirm_button.click()
            await safe_sleep(0.3)

        # 提交后再次检测验证码
        await handle_captcha(page)

        # 等待是否带到支付页面（移动端 H5 + PC 端 fallback）
        try:
            await page.wait_for_selector(
                'text="去支付", text="立即支付", text="付款"',
                timeout=10000
            )
            return True
        except Exception:
            pass
        return True
    except Exception as e:
        log(f'提交订单失败: {e}')
    return False


async def refresh_inventory(page: Page):
    try:
        await page.reload(timeout=30000)
        await random_navigation_delay()
        log('已刷新库存/页面。')
    except Exception as e:
        log(f'刷新页面失败: {e}')


@auto_reconnect_decorator(max_retries=3)
async def attempt_purchase(context: BrowserContext, config: Dict, task_id: int):
    page = await context.new_page()

    # 从新格式嵌套结构读取配置
    concert = config.get('concert', {})
    ticket = config.get('ticket', {})
    engine = config.get('engine', {})

    concert_name = concert.get('name', '') or config.get('concert_name', '')
    city = concert.get('city', '') or config.get('city', '')
    date = concert.get('date', '') or config.get('date', '')
    target_session = ticket.get('session', '') or config.get('target_session', '')
    price_target = ticket.get('prices', []) or config.get('prices', config.get('price', 0))
    ticket_count = int(ticket.get('count', 1) or config.get('ticket_count', 1))
    interval = float(engine.get('interval', 0.3) or config.get('interval', 0.3))
    retry_count = int(engine.get('retry_count', 999) or config.get('retry_count', 999))
    consecutive_error_threshold = int(config.get('concurrency_control', {}).get('consecutive_error_pause_threshold', 5))

    # ID 直达相关字段（从 concert 段读取）
    event_id = concert.get('event_id', '') or config.get('event_id', '')
    session_id = concert.get('session_id', '') or config.get('session_id', '')
    ticket_id = concert.get('ticket_id', '') or config.get('ticket_id', '')

    # 观演人信息
    viewers = config.get('viewers', [])

    # 如果有 event_id，直接构造移动端 H5 详情页URL，跳过搜索
    cached_concert_url = None
    if event_id:
        cached_concert_url = get_mobile_detail_url(event_id)
        log(f'[任务{task_id}] 使用 event_id={event_id} 直达移动端详情页: {cached_concert_url}')

    consecutive_errors = 0

    for attempt in range(1, retry_count + 1):
        # 连续错误超过阈值时，短暂暂停后恢复
        if consecutive_errors >= consecutive_error_threshold:
            log(f'[任务{task_id}] 连续错误 {consecutive_errors} 次，暂停 2 秒后恢复')
            await safe_sleep(2)
            consecutive_errors = 0

        # 固定间隔 + 随机抖动
        retry_delay = interval + random.uniform(0, 0.15)

        try:
            log(f'[任务{task_id}] 第 {attempt} 次抢票开始')

            if cached_concert_url:
                # 有 event_id 或已缓存演出URL，直接访问，跳过搜索（省3-5秒）
                await page.goto(cached_concert_url, timeout=30000)
                await random_navigation_delay()
            else:
                # 无 event_id，走搜索流程（降级方案）
                await find_concert_page(page, concert_name, city, date)
                current_url = page.url
                if 'detail.damai.cn' in current_url or 'item.htm' in current_url or 'm.damai.cn' in current_url:
                    cached_concert_url = current_url
                    log(f'[任务{task_id}] 缓存演出页面URL: {cached_concert_url}')

            await select_session_and_price(page, target_session, price_target, session_id, ticket_id)
            success = await submit_order(page, ticket_count, viewers)
            if success:
                log(f'[任务{task_id}] 抢票成功，已进入支付页面。')

                # 播放成功声音
                beep_success()

                # 截图保存
                screenshot_path = None
                try:
                    screenshot_path = await capture_success_screenshot(
                        page,
                        {
                            'concert_name': concert_name,
                            'target_session': target_session,
                            'price_target': price_target,
                            'task_id': task_id,
                            'timestamp': time.time()
                        }
                    )
                    if screenshot_path:
                        log(f'[任务{task_id}] 截图已保存: {screenshot_path}')
                except Exception as e:
                    log(f'[任务{task_id}] 截图失败: {e}')

                # 显示增强通知（跨平台：声音 + 系统通知）
                if config.get('notifications', {}).get('sound', True) or config.get('enable_notifications', True):
                    notify_success_v2(
                        '大麦抢票成功',
                        f'演出：{concert_name}\n场次：{target_session}\n票价：{price_target}'
                    )

                consecutive_errors = 0
                return True

            # 固定间隔重试
            consecutive_errors += 1
            log(f'[任务{task_id}] 抢票未成功，等待 {retry_delay:.2f}s 重试。')
            await safe_sleep(retry_delay)
            await refresh_inventory(page)
        except Exception as e:
            consecutive_errors += 1
            err_msg = str(e).lower()
            # 错误分类日志
            if 'net::' in err_msg or 'timeout' in err_msg or 'connection' in err_msg:
                log_network_error(logger, f'[任务{task_id}] 异常：{e}，继续重试')
            elif '登录' in err_msg or 'login' in err_msg or 'session' in err_msg or 'cookie' in err_msg:
                log_login_error(logger, f'[任务{task_id}] 异常：{e}，继续重试')
            elif '验证码' in err_msg or 'captcha' in err_msg or 'verify' in err_msg:
                log_captcha_error(logger, f'[任务{task_id}] 异常：{e}，继续重试')
            elif '库存' in err_msg or 'stock' in err_msg or 'sold' in err_msg:
                log_stock_error(logger, f'[任务{task_id}] 异常：{e}，继续重试')
            else:
                log(f'[任务{task_id}] 异常：{e}，继续重试')
            # 如果页面导航失败（可能是缓存URL失效），清除缓存重新搜索
            if 'net::' in str(e) or 'Timeout' in str(e):
                cached_concert_url = None
                log(f'[任务{task_id}] URL可能失效，下次重新搜索')
            # 检查页面是否仍然有效，如果无效则创建新页面；否则复用当前页面
            if page.is_closed():
                log(f'[任务{task_id}] 页面已关闭，创建新页面')
                page = await context.new_page()
                cached_concert_url = None
            else:
                try:
                    await page.reload(timeout=15000)
                except Exception:
                    pass
            await safe_sleep(retry_delay)
    log(f'[任务{task_id}] 达到最大重试次数({retry_count})，停止任务。')
    return False


async def run_tasks(context: BrowserContext, config: Dict):
    """
    使用策略模式执行抢票任务
    保持向后兼容：如果配置中没有strategy字段，使用并发策略
    """
    try:
        from .strategies import StrategyFactory
        strategy = StrategyFactory.create_strategy(config)
        return await strategy.execute(context)
    except ImportError:
        # 如果strategies模块不可用，则使用旧版并发逻辑
        engine = config.get('engine', {})
        concurrency = int(engine.get('concurrency', 3) or config.get('concurrency', 3))
        max_concurrency = concurrency
        semaphore = asyncio.Semaphore(max_concurrency)

        async def task_with_semaphore(task_id):
            async with semaphore:
                return await attempt_purchase(context, config, task_id)

        jobs = []
        for task_id in range(1, concurrency + 1):
            jobs.append(task_with_semaphore(task_id))
        results = await asyncio.gather(*jobs, return_exceptions=True)
        return results


async def preload_page(context: BrowserContext, config: Dict) -> dict:
    """
    预加载页面：打开浏览器 -> 登录 -> 进入详情页 -> 选好场次票价

    Args:
        context: 浏览器上下文
        config: 抢票配置（嵌套结构）

    Returns:
        dict: {"page": page对象, "cached_url": 缓存的URL} 或 None
    """
    try:
        # 从配置读取参数
        concert = config.get('concert', {})
        ticket = config.get('ticket', {})

        concert_name = concert.get('name', '') or config.get('concert_name', '')
        city = concert.get('city', '') or config.get('city', '')
        date = concert.get('date', '') or config.get('date', '')
        target_session = ticket.get('session', '') or config.get('target_session', '')
        price_target = ticket.get('prices', []) or config.get('prices', config.get('price', 0))

        # ID 直达相关字段
        event_id = concert.get('event_id', '') or config.get('event_id', '')
        session_id = concert.get('session_id', '') or config.get('session_id', '')
        ticket_id = concert.get('ticket_id', '') or config.get('ticket_id', '')

        log('[预加载] 开始预加载页面...')

        # 创建页面
        page = await context.new_page()

        # 导航到详情页（移动端 H5）
        if event_id:
            # 有 event_id，直接构造移动端 H5 详情页URL
            concert_url = get_mobile_detail_url(event_id)
            log(f'[预加载] 使用 event_id={event_id} 直达移动端详情页: {concert_url}')
            await page.goto(concert_url, timeout=60000)
        else:
            # 无 event_id，走搜索流程
            log(f'[预加载] 搜索演出: {concert_name}')
            await find_concert_page(page, concert_name, city, date)

        await safe_sleep(0.5)

        # 选择场次和票价
        log(f'[预加载] 选择场次: {target_session}, 票价: {price_target}')
        await select_session_and_price(page, target_session, price_target, session_id, ticket_id)

        # 缓存当前URL
        cached_url = page.url
        log(f'[预加载] 页面预加载完成，URL: {cached_url}')

        return {"page": page, "cached_url": cached_url}

    except Exception as e:
        log(f'[预加载] 预加载失败: {e}')
        return None


async def wait_and_buy(page: Page, config: Dict, target_time: datetime.datetime) -> bool:
    """
    轮询等待购票按钮可点击 -> 立即点击 -> 提交订单

    Args:
        page: 已预加载的页面对象（停留在购票页）
        config: 抢票配置
        target_time: 开售时间

    Returns:
        bool: 是否抢票成功
    """
    try:
        ticket = config.get('ticket', {})
        ticket_count = int(ticket.get('count', 1) or config.get('ticket_count', 1))

        concert = config.get('concert', {})
        concert_name = concert.get('name', '') or config.get('concert_name', '')
        target_session = ticket.get('session', '') or config.get('target_session', '')
        price_target = ticket.get('prices', []) or config.get('prices', config.get('price', 0))

        # 观演人信息
        viewers = config.get('viewers', [])

        log('[抢票] 进入待命状态，等待开售...')

        # 精确等待到开售时间（使用 time.perf_counter 高精度）
        target_ts = target_time.timestamp()
        while True:
            now_ts = time.time()
            remaining = target_ts - now_ts
            if remaining <= 0:
                break
            elif remaining > 1:
                time.sleep(0.5)
            elif remaining > 0.01:
                time.sleep(0.005)
            # 最后10ms: 忙等待（自旋），不调用sleep

        log(f'[抢票] 开售时间到! 开始点击购买按钮...')

        # 购买按钮选择器列表（多种可能的按钮文本，兼容新旧版本）
        buy_selectors = [
            'div.buy-link',
            'text="不，立即购票"',
            'text="不，立即预订"',
            'text="不，选座购票"',
            'text="不，立即抢票"',
            'button:has-text("立即抢票")',
            'button:has-text("立即购买")',
            'button:has-text("立即预订")',
            'button:has-text("选座购买")',
            'a:has-text("立即抢票")',
            'a:has-text("立即购买")',
            'a:has-text("立即预订")',
        ]

        # 毫秒级轮询点击购买按钮
        max_click_attempts = 50
        for attempt in range(max_click_attempts):
            try:
                for selector in buy_selectors:
                    buy_btn = await page.query_selector(selector)
                    if buy_btn:
                        # 检查按钮是否可点击（非disabled）
                        is_disabled = await buy_btn.get_attribute('disabled')
                        if is_disabled:
                            continue

                        # 立即点击
                        log(f'[抢票] 找到购买按钮，第 {attempt + 1} 次尝试点击...')
                        await buy_btn.click()
                        await safe_sleep(0.5)

                        # 点击后检测验证码
                        await handle_captcha(page)

                        # 处理登录重定向（新版大麦网点击购买后会跳转登录页）
                        current_url = page.url
                        if 'passport.damai.cn/login' in current_url or 'login' in current_url:
                            log('[抢票] 已跳转到登录页，等待登录完成...')
                            try:
                                await page.wait_for_url('**/buy**', timeout=120000)
                                log('[抢票] 登录完成，已进入购买页面')
                                await safe_sleep(0.5)
                            except Exception:
                                await safe_sleep(2)

                        # 提交订单
                        success = await _submit_order_fast(page, ticket_count, viewers)
                        if success:
                            log(f'[抢票] 抢票成功! 已进入支付页面')

                            # 播放成功声音
                            beep_success()

                            # 截图保存
                            try:
                                screenshot_path = await capture_success_screenshot(
                                    page,
                                    {
                                        'concert_name': concert_name,
                                        'target_session': target_session,
                                        'price_target': price_target,
                                        'timestamp': time.time()
                                    }
                                )
                                if screenshot_path:
                                    log(f'[抢票] 截图已保存: {screenshot_path}')
                            except Exception as e:
                                log(f'[抢票] 截图失败: {e}')

                            # 显示通知（跨平台：声音 + 系统通知）
                            if config.get('notifications', {}).get('sound', True):
                                notify_success_v2(
                                    '大麦抢票成功',
                                    f'演出：{concert_name}\n场次：{target_session}\n票价：{price_target}'
                                )

                            return True

            except Exception as e:
                err_msg = str(e).lower()
                if 'net::' in err_msg or 'timeout' in err_msg or 'connection' in err_msg:
                    log_network_error(logger, f'[抢票] 点击异常: {e}')
                elif '验证码' in err_msg or 'captcha' in err_msg or 'verify' in err_msg:
                    log_captcha_error(logger, f'[抢票] 点击异常: {e}')
                elif '库存' in err_msg or 'stock' in err_msg or 'sold' in err_msg:
                    log_stock_error(logger, f'[抢票] 点击异常: {e}')
                else:
                    log(f'[抢票] 点击异常: {e}')

            # 极短间隔重试
            await safe_sleep(0.05)

            # 每10次尝试刷新一次页面
            if attempt > 0 and attempt % 10 == 0:
                try:
                    await page.reload(timeout=5000)
                    await safe_sleep(0.2)
                    # 重新选择场次和票价
                    await select_session_and_price(page, target_session, price_target)
                except Exception:
                    pass

        log(f'[抢票] 达到最大点击尝试次数({max_click_attempts})，抢票失败')
        return False

    except Exception as e:
        err_msg = str(e).lower()
        if 'net::' in err_msg or 'timeout' in err_msg or 'connection' in err_msg:
            log_network_error(logger, f'[抢票] 异常: {e}')
        elif '登录' in err_msg or 'login' in err_msg or 'session' in err_msg:
            log_login_error(logger, f'[抢票] 异常: {e}')
        else:
            log(f'[抢票] 异常: {e}')
        return False


async def _submit_order_fast(page: Page, ticket_count: int = 1, viewers: list = None) -> bool:
    """
    快速提交订单（优化速度版本）

    Args:
        page: 页面对象
        ticket_count: 购票数量
        viewers: 观演人列表

    Returns:
        bool: 是否提交成功
    """
    try:
        # 订单确认页，选择票数
        if ticket_count > 1:
            try:
                qty = await page.query_selector(
                    'select.ticket-count, input.ticket-count, '
                    'input[class*="num"], input[class*="quantity"]'
                )
                if qty:
                    await qty.fill(str(ticket_count))
            except Exception:
                pass

        # 选择观演人
        if viewers:
            try:
                await select_viewers(page, viewers)
            except Exception as e:
                log(f'观演人选择失败，继续提交: {e}')

        # 检测验证码
        await handle_captcha(page)

        # 快速查找并点击确认按钮（移动端 H5 + PC 端 fallback）
        confirm_selectors = [
            'button:has-text("提交订单")',
            'button:has-text("确认")',
            'text="立即提交"',
            'span:text("立即提交")',
            'button:has-text("确认购买")',
            'button:has-text("去结算")',
            'button:has-text("确认订单")',
            'button:has-text("立即支付")',
        ]

        for selector in confirm_selectors:
            confirm_button = await page.query_selector(selector)
            if confirm_button:
                await confirm_button.click()
                break

        # 提交后检测验证码
        await handle_captcha(page)

        # 等待支付页面（移动端 H5 + PC 端 fallback）
        try:
            await page.wait_for_selector('text="去支付", text="立即支付", text="付款"', timeout=10000)
            return True
        except Exception:
            # 可能页面跳转到了其他确认页，再尝试一次
            for selector in confirm_selectors:
                confirm_button = await page.query_selector(selector)
                if confirm_button:
                    await confirm_button.click()
                    await safe_sleep(0.3)

            await page.wait_for_selector('text="去支付", text="立即支付", text="付款"', timeout=5000)
            return True

    except Exception as e:
        log(f'[抢票] 提交订单失败: {e}')
    return False
