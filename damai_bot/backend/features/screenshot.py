"""
大麦抢票系统 - 截图功能模块

本文件为 Web 自动化技术学习示例，仅供开发者学习研究使用。

技术要点：
- Playwright 页面截图 API
- 自动水印添加（PIL/Pillow）
- 截图文件自动清理（FIFO 策略）
- 带重试的截图机制

作者：小吴 (Xiao Wu)
许可证：MIT
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Optional, Union, Dict, Any
from pathlib import Path

from backend.utils import log

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ScreenshotManager:
    """截图管理器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        screenshot_config = self.config.get('screenshot', {})

        # 截图配置
        self.enabled = screenshot_config.get('enabled', True)
        self.save_path = screenshot_config.get('save_path', './screenshots')
        self.format = screenshot_config.get('format', 'png').lower()
        self.quality = screenshot_config.get('quality', 90)
        self.add_timestamp = screenshot_config.get('add_timestamp', True)
        self.add_watermark = screenshot_config.get('add_watermark', False)
        self.max_screenshots = screenshot_config.get('max_screenshots', 100)

        # 创建保存目录
        os.makedirs(self.save_path, exist_ok=True)

        # 截图计数器
        self.screenshot_count = 0

    def _generate_filename(self, prefix: str = "success") -> str:
        """生成截图文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshot_count += 1
        count_str = f"_{self.screenshot_count:04d}"

        if self.add_timestamp:
            filename = f"{prefix}_{timestamp}{count_str}.{self.format}"
        else:
            filename = f"{prefix}{count_str}.{self.format}"

        return os.path.join(self.save_path, filename)

    async def capture_page(self, page, full_page: bool = True,
                          element_selector: Optional[str] = None) -> Optional[str]:
        """
        截取页面或元素

        :param page: Playwright Page 对象
        :param full_page: 是否截取整个页面
        :param element_selector: 元素选择器（如果指定，则截取该元素）
        :return: 截图文件路径，失败返回 None
        """
        if not self.enabled:
            return None

        try:
            # 生成文件名
            filename = self._generate_filename("ticket_success")

            # 截图选项
            screenshot_options = {
                'path': filename,
                'type': self.format,
                'quality': self.quality if self.format == 'jpeg' else None,
                'full_page': full_page
            }

            # 截取元素或整个页面
            if element_selector:
                element = await page.query_selector(element_selector)
                if element:
                    await element.screenshot(**screenshot_options)
                    log(f"元素截图已保存: {filename}")
                else:
                    log(f"未找到元素: {element_selector}，改为全屏截图")
                    await page.screenshot(**screenshot_options)
                    log(f"全屏截图已保存: {filename}")
            else:
                await page.screenshot(**screenshot_options)
                log(f"截图已保存: {filename}")

            # 添加水印
            if self.add_watermark and PIL_AVAILABLE:
                self._add_watermark(filename)

            # 清理旧截图
            self._cleanup_old_screenshots()

            return filename

        except Exception as e:
            log(f"截图失败: {e}")
            return None

    async def capture_success(self, page, context: Dict[str, Any] = None) -> Optional[str]:
        """
        抢票成功截图

        :param page: Playwright Page 对象
        :param context: 上下文信息（演出名称、票价等）
        :return: 截图文件路径
        """
        if not self.enabled:
            return None

        try:
            # 截取整个页面
            filename = await self.capture_page(page, full_page=True)

            if filename and context:
                # 保存上下文信息到 JSON 文件
                info_file = filename.replace(f'.{self.format}', '.json')
                import json
                with open(info_file, 'w', encoding='utf-8') as f:
                    json.dump(context, f, ensure_ascii=False, indent=2)

            return filename

        except Exception as e:
            log(f"抢票成功截图失败: {e}")
            return None

    async def capture_element(self, page, selector: str,
                             context: Dict[str, Any] = None) -> Optional[str]:
        """
        截取特定元素

        :param page: Playwright Page 对象
        :param selector: 元素选择器
        :param context: 上下文信息
        :return: 截图文件路径
        """
        if not self.enabled:
            return None

        try:
            filename = await self.capture_page(page, full_page=False,
                                              element_selector=selector)

            if filename and context:
                # 保存上下文信息
                info_file = filename.replace(f'.{self.format}', '.json')
                import json
                with open(info_file, 'w', encoding='utf-8') as f:
                    json.dump(context, f, ensure_ascii=False, indent=2)

            return filename

        except Exception as e:
            log(f"元素截图失败: {e}")
            return None

    def _add_watermark(self, image_path: str):
        """添加水印"""
        if not PIL_AVAILABLE:
            return

        try:
            image = Image.open(image_path)
            from PIL import ImageDraw, ImageFont

            # 创建绘图对象
            draw = ImageDraw.Draw(image)

            # 加载字体
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()

            # 水印文本
            watermark_text = f"大麦抢票 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # 计算文本位置（右下角）
            text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            margin = 10
            x = image.width - text_width - margin
            y = image.height - text_height - margin

            # 绘制背景矩形
            draw.rectangle(
                [x - 5, y - 5, x + text_width + 5, y + text_height + 5],
                fill=(0, 0, 0, 128)  # 半透明黑色
            )

            # 绘制文本
            draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255))

            # 保存图片
            image.save(image_path)
            log(f"已添加水印: {image_path}")

        except Exception as e:
            log(f"添加水印失败: {e}")

    def _cleanup_old_screenshots(self):
        """清理旧截图"""
        try:
            if self.max_screenshots <= 0:
                return

            # 获取所有截图文件
            screenshot_files = []
            for ext in ['.png', '.jpg', '.jpeg']:
                screenshot_files.extend(Path(self.save_path).glob(f'*{ext}'))

            # 按修改时间排序
            screenshot_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # 删除超出数量限制的文件
            if len(screenshot_files) > self.max_screenshots:
                files_to_delete = screenshot_files[self.max_screenshots:]
                for file in files_to_delete:
                    try:
                        # 同时删除对应的 JSON 文件
                        json_file = file.with_suffix('.json')
                        if json_file.exists():
                            json_file.unlink()

                        file.unlink()
                        log(f"已删除旧截图: {file.name}")
                    except Exception as e:
                        log(f"删除文件失败 {file}: {e}")

        except Exception as e:
            log(f"清理旧截图失败: {e}")

    async def capture_with_retry(self, page, retries: int = 3,
                                delay: float = 1.0) -> Optional[str]:
        """
        带重试的截图

        :param page: Playwright Page 对象
        :param retries: 重试次数
        :param delay: 重试延迟（秒）
        :return: 截图文件路径
        """
        for attempt in range(retries):
            try:
                filename = await self.capture_page(page, full_page=True)
                if filename:
                    return filename
            except Exception as e:
                log(f"截图重试 {attempt + 1}/{retries} 失败: {e}")

            if attempt < retries - 1:
                await asyncio.sleep(delay)

        return None


# 全局截图管理器实例
screenshot_manager = ScreenshotManager()


async def capture_success_screenshot(page, context: Dict[str, Any] = None) -> Optional[str]:
    """
    抢票成功截图（简化接口）
    """
    return await screenshot_manager.capture_success(page, context)


async def capture_element_screenshot(page, selector: str,
                                    context: Dict[str, Any] = None) -> Optional[str]:
    """
    截取元素截图（简化接口）
    """
    return await screenshot_manager.capture_element(page, selector, context)


def set_screenshot_config(config: Dict[str, Any]):
    """设置截图配置"""
    global screenshot_manager
    screenshot_manager = ScreenshotManager(config)