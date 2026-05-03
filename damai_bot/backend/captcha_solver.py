"""
大麦抢票系统 - 验证码识别模块

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。
请勿用于任何商业或非法用途。使用前请阅读项目根目录下的 DISCLAIMER.md。

技术要点：
- 使用 ddddocr 开源库进行图形验证码 OCR 识别
- 滑块验证码缺口位置识别与拖拽轨迹生成
- 支持图片验证码、滑块验证码、点选验证码的自动检测
- 物理模拟的拖拽轨迹（加速-减速-回弹）

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import asyncio
import base64
import io
import time
from typing import Optional

try:
    import ddddocr
    DDDDOCR_AVAILABLE = True
except ImportError:
    DDDDOCR_AVAILABLE = False

from backend.logger import get_logger, log_captcha_error

logger = get_logger(__name__)

# 最大重试次数
MAX_RETRIES = 3

# ddddocr 实例（延迟初始化）
_ocr_instance: Optional[object] = None
_slide_instance: Optional[object] = None


def _get_ocr():
    """获取或创建 ddddocr 文字识别实例"""
    global _ocr_instance
    if not DDDDOCR_AVAILABLE:
        raise ImportError("ddddocr 未安装，请执行: pip install ddddocr")
    if _ocr_instance is None:
        _ocr_instance = ddddocr.DdddOcr(show_ad=False)
    return _ocr_instance


def _get_slide():
    """获取或创建 ddddocr 滑块识别实例"""
    global _slide_instance
    if not DDDDOCR_AVAILABLE:
        raise ImportError("ddddocr 未安装，请执行: pip install ddddocr")
    if _slide_instance is None:
        _slide_instance = ddddocr.DdddOcr(det=False, show_ad=False)
    return _slide_instance


async def detect_captcha_type(page) -> str:
    """
    检测页面上出现的验证码类型

    Returns:
        "slider"   - 滑块拼图验证码
        "image"    - 图片文字验证码
        "click"    - 点选验证码
        "none"     - 无验证码
    """
    try:
        # 滑块验证码：常见选择器
        slider_selectors = [
            "#nc_1_n1z",                          # 淘宝系滑块
            ".nc-container .nc_scale",             # 淘宝滑块容器
            ".slider-captcha",                     # 通用滑块
            ".geetest_slider_button",              # 极验滑块
            "#captcha .slider",                    # 大麦滑块
            ".captcha-slider",                     # 通用
            "[class*='slider'][class*='captcha']", # 模糊匹配
            ".slide-verify-slider",                # 滑块验证
        ]
        for sel in slider_selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    logger.info(f"[CAPTCHA] 检测到滑块验证码: {sel}")
                    return "slider"
            except Exception:
                continue

        # 图片文字验证码
        image_selectors = [
            "#captcha img",
            ".captcha-img",
            "img[alt*='验证码']",
            "img[src*='captcha']",
            "img[src*='verify']",
            ".verify-img img",
            "[class*='captcha'] img",
        ]
        for sel in image_selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    logger.info(f"[CAPTCHA] 检测到图片验证码: {sel}")
                    return "image"
            except Exception:
                continue

        # 点选验证码
        click_selectors = [
            ".click-captcha",
            ".verify-click",
            ".geetest_click",
            "[class*='click'][class*='captcha']",
            ".captcha-click",
        ]
        for sel in click_selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    logger.info(f"[CAPTCHA] 检测到点选验证码: {sel}")
                    return "click"
            except Exception:
                continue

        return "none"

    except Exception as e:
        log_captcha_error(logger, f"检测验证码类型异常: {e}")
        return "none"


async def _screenshot_element(page, selector: str) -> Optional[bytes]:
    """截取指定元素的截图，返回 PNG 字节"""
    try:
        el = await page.query_selector(selector)
        if el and await el.is_visible():
            return await el.screenshot()
    except Exception as e:
        logger.debug(f"截图元素 {selector} 失败: {e}")
    return None


async def solve_captcha(page) -> bool:
    """
    检测并处理图片文字验证码

    流程：
    1. 检测验证码图片元素
    2. 截图并用 ddddocr 识别
    3. 填入输入框并提交

    Returns:
        True  - 识别并填写成功
        False - 无验证码或识别失败
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            captcha_type = await detect_captcha_type(page)
            if captcha_type != "image":
                return captcha_type == "none"

            logger.info(f"[CAPTCHA] 开始识别图片验证码 (第{attempt}次)")

            # 截取验证码图片
            img_selectors = [
                "#captcha img",
                ".captcha-img",
                "img[alt*='验证码']",
                "img[src*='captcha']",
                "img[src*='verify']",
                ".verify-img img",
                "[class*='captcha'] img",
            ]

            img_bytes = None
            for sel in img_selectors:
                img_bytes = await _screenshot_element(page, sel)
                if img_bytes:
                    break

            if not img_bytes:
                logger.warning("[CAPTCHA] 无法截取验证码图片")
                return False

            # ddddocr 识别
            ocr = _get_ocr()
            result = ocr.classification(img_bytes)
            result = result.strip().replace(" ", "")

            if not result:
                logger.warning("[CAPTCHA] ddddocr 识别结果为空")
                continue

            logger.info(f"[CAPTCHA] 识别结果: {result}")

            # 填写验证码
            input_selectors = [
                "#captcha input",
                ".captcha-input",
                "input[placeholder*='验证码']",
                "input[name*='captcha']",
                "input[name*='verify']",
                "[class*='captcha'] input",
            ]

            filled = False
            for sel in input_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        await el.fill("")
                        await el.type(result, delay=50)
                        filled = True
                        logger.info(f"[CAPTCHA] 已填入验证码到: {sel}")
                        break
                except Exception:
                    continue

            if not filled:
                logger.warning("[CAPTCHA] 未找到验证码输入框")
                return False

            # 尝试点击确认按钮
            submit_selectors = [
                "#captcha .submit",
                ".captcha-submit",
                "button[type='submit']",
                ".verify-btn",
                "[class*='captcha'] button",
            ]
            for sel in submit_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click()
                        logger.info(f"[CAPTCHA] 已点击确认按钮: {sel}")
                        break
                except Exception:
                    continue

            await asyncio.sleep(0.5)
            logger.info("[CAPTCHA] 图片验证码处理完成")
            return True

        except ImportError:
            raise
        except Exception as e:
            log_captcha_error(logger, f"识别图片验证码异常 (第{attempt}次): {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(0.5)

    logger.error("[CAPTCHA] 图片验证码识别重试耗尽")
    return False


async def solve_slider(page) -> bool:
    """
    检测并处理滑块验证码

    流程：
    1. 截取滑块背景图和滑块图
    2. 用 ddddocr 识别缺口偏移量
    3. 模拟拖拽滑块到目标位置

    Returns:
        True  - 处理成功
        False - 无滑块或处理失败
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            captcha_type = await detect_captcha_type(page)
            if captcha_type != "slider":
                return captcha_type == "none"

            logger.info(f"[CAPTCHA] 开始处理滑块验证码 (第{attempt}次)")

            # 尝试获取背景图和滑块图
            bg_selectors = [
                ".slide-verify-image img",
                ".captcha-bg img",
                ".geetest_canvas_bg",
                ".captcha-slider-bg img",
                "[class*='slide'] img:first-child",
                ".verify-img-panel img",
            ]
            slice_selectors = [
                ".slide-verify-block",
                ".captcha-slice",
                ".geetest_canvas_slice",
                "[class*='slide'] img:nth-child(2)",
                ".verify-sub-block",
            ]

            bg_bytes = None
            for sel in bg_selectors:
                bg_bytes = await _screenshot_element(page, sel)
                if bg_bytes:
                    break

            slice_bytes = None
            for sel in slice_selectors:
                slice_bytes = await _screenshot_element(page, sel)
                if slice_bytes:
                    break

            if bg_bytes and slice_bytes:
                # 用 ddddocr 滑块识别
                slide = _get_slide()
                result = slide.slide_match(slice_bytes, bg_bytes, simple_target=True)
                if result and "target" in result:
                    target_x = result["target"][0]
                    logger.info(f"[CAPTCHA] 滑块缺口偏移: {target_x}px")
                else:
                    logger.warning("[CAPTCHA] ddddocr 未能识别滑块缺口")
                    continue
            else:
                # 降级：尝试截图整个滑块容器，用通用偏移
                container_selectors = [
                    ".slide-verify",
                    ".captcha-slider",
                    ".geetest_panel",
                    "[class*='captcha'][class*='slider']",
                    ".verify-wrap",
                ]
                container_bytes = None
                for sel in container_selectors:
                    container_bytes = await _screenshot_element(page, sel)
                    if container_bytes:
                        break

                if not container_bytes:
                    logger.warning("[CAPTCHA] 无法截取滑块验证码区域")
                    return False

                # 用通用比例估算（大约 60% 位置）
                slide = _get_slide()
                result = slide.slide_match(container_bytes, container_bytes, simple_target=True)
                if result and "target" in result:
                    target_x = int(result["target"][0] * 0.6)
                else:
                    target_x = 200  # 兜底值
                logger.info(f"[CAPTCHA] 滑块估算偏移: {target_x}px")

            # 查找滑块按钮并拖拽
            slider_btn_selectors = [
                "#nc_1_n1z",
                ".nc_scale .btn_slide",
                ".slider-btn",
                ".geetest_slider_button",
                ".slide-verify-slider-mask-item",
                "[class*='slider'][class*='btn']",
                "[class*='slide'][class*='drag']",
            ]

            slider_btn = None
            for sel in slider_btn_selectors:
                slider_btn = await page.query_selector(sel)
                if slider_btn and await slider_btn.is_visible():
                    break

            if not slider_btn:
                logger.warning("[CAPTCHA] 未找到滑块拖拽按钮")
                return False

            # 模拟人类拖拽轨迹
            box = await slider_btn.bounding_box()
            if not box:
                logger.warning("[CAPTCHA] 无法获取滑块按钮位置")
                return False

            start_x = box["x"] + box["width"] / 2
            start_y = box["y"] + box["height"] / 2

            await page.mouse.move(start_x, start_y)
            await page.mouse.down()
            await asyncio.sleep(0.1)

            # 分步移动，模拟人类轨迹
            steps = _generate_track(target_x)
            current_x = start_x
            for dx, dy, dt in steps:
                current_x += dx
                await page.mouse.move(current_x, start_y + dy)
                await asyncio.sleep(dt)

            await asyncio.sleep(0.1)
            await page.mouse.up()
            await asyncio.sleep(0.5)

            logger.info("[CAPTCHA] 滑块验证码处理完成")
            return True

        except ImportError:
            raise
        except Exception as e:
            log_captcha_error(logger, f"处理滑块验证码异常 (第{attempt}次): {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(0.5)

    logger.error("[CAPTCHA] 滑块验证码处理重试耗尽")
    return False


def _generate_track(distance: int):
    """
    生成模拟人类的滑块拖拽轨迹

    Args:
        distance: 目标拖拽距离 (px)

    Yields:
        (dx, dy, delay) 每步的位移和延迟
    """
    import random

    tracks = []
    current = 0
    mid = distance * 0.7
    v = 0
    t = 0.2

    while current < distance:
        if current < mid:
            a = random.uniform(2, 4)
        else:
            a = -random.uniform(1, 3)

        v0 = v
        v = v0 + a * t
        if v < 0.5:
            v = 0.5
        dx = v0 * t + 0.5 * a * t * t
        dx = max(1, int(dx))

        if current + dx > distance:
            dx = distance - current

        dy = random.randint(-1, 1)
        dt = random.uniform(0.01, 0.03)
        tracks.append((dx, dy, dt))
        current += dx

    # 添加少量回弹
    for _ in range(random.randint(1, 3)):
        tracks.append((random.randint(-2, -1), random.randint(-1, 1), random.uniform(0.05, 0.1)))

    return tracks
