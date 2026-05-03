#!/usr/bin/env python3
"""
Cookie 管理模块
用于保存、加载和验证大麦网登录Cookie
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Cookie文件路径
COOKIE_FILE = "config/cookies.json"


class CookieManager:
    """Cookie管理器"""

    @staticmethod
    def save_cookies(cookies: List[Dict[str, Any]], file_path: str = COOKIE_FILE) -> bool:
        """
        保存Cookie到文件

        Args:
            cookies: Cookie列表，每个Cookie是字典格式
            file_path: 保存路径，默认为config/cookies.json

        Returns:
            bool: 是否保存成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 添加保存时间戳
            cookie_data = {
                "saved_at": datetime.now().isoformat(),
                "cookies": cookies
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Cookie已保存到 {file_path}, 共 {len(cookies)} 个cookie")
            return True

        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
            return False

    @staticmethod
    def load_cookies(file_path: str = COOKIE_FILE) -> Optional[List[Dict[str, Any]]]:
        """
        从文件加载Cookie

        Args:
            file_path: 文件路径，默认为config/cookies.json

        Returns:
            Optional[List[Dict]]: Cookie列表，如果文件不存在或格式错误返回None
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Cookie文件不存在: {file_path}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)

            # 检查数据格式
            if isinstance(cookie_data, dict) and 'cookies' in cookie_data:
                cookies = cookie_data['cookies']
                saved_at = cookie_data.get('saved_at', '未知时间')
                logger.info(f"从 {file_path} 加载Cookie, 保存于 {saved_at}, 共 {len(cookies)} 个cookie")
                return cookies
            elif isinstance(cookie_data, list):
                # 兼容旧格式（直接是Cookie列表）
                logger.info(f"从 {file_path} 加载Cookie（旧格式）, 共 {len(cookie_data)} 个cookie")
                return cookie_data
            else:
                logger.error(f"Cookie文件格式错误: {file_path}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Cookie文件JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"加载Cookie失败: {e}")
            return None

    @staticmethod
    def get_cookie_file_info(file_path: str = COOKIE_FILE) -> Optional[Dict[str, Any]]:
        """
        获取Cookie文件信息

        Args:
            file_path: 文件路径

        Returns:
            Optional[Dict]: 文件信息，包含保存时间、cookie数量等
        """
        try:
            if not os.path.exists(file_path):
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)

            file_stat = os.stat(file_path)

            info = {
                "file_path": file_path,
                "file_size": file_stat.st_size,
                "modified_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                "exists": True
            }

            if isinstance(cookie_data, dict) and 'cookies' in cookie_data:
                info.update({
                    "saved_at": cookie_data.get('saved_at', '未知时间'),
                    "cookie_count": len(cookie_data['cookies']),
                    "format": "new"
                })
            elif isinstance(cookie_data, list):
                info.update({
                    "saved_at": "未知时间（旧格式）",
                    "cookie_count": len(cookie_data),
                    "format": "old"
                })
            else:
                info.update({
                    "saved_at": "未知时间",
                    "cookie_count": 0,
                    "format": "invalid"
                })

            return info

        except Exception as e:
            logger.error(f"获取Cookie文件信息失败: {e}")
            return None

    @staticmethod
    def delete_cookies(file_path: str = COOKIE_FILE) -> bool:
        """
        删除Cookie文件

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否删除成功
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cookie文件已删除: {file_path}")
                return True
            else:
                logger.warning(f"Cookie文件不存在: {file_path}")
                return False
        except Exception as e:
            logger.error(f"删除Cookie文件失败: {e}")
            return False

    @staticmethod
    def cookies_to_json(cookies: List[Dict[str, Any]]) -> str:
        """
        将Cookie列表转换为JSON字符串

        Args:
            cookies: Cookie列表

        Returns:
            str: JSON字符串
        """
        try:
            return json.dumps(cookies, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Cookie转换为JSON失败: {e}")
            return "[]"

    @staticmethod
    def json_to_cookies(cookies_json: str) -> Optional[List[Dict[str, Any]]]:
        """
        将JSON字符串转换为Cookie列表

        Args:
            cookies_json: JSON字符串

        Returns:
            Optional[List[Dict]]: Cookie列表
        """
        try:
            cookies = json.loads(cookies_json)
            if isinstance(cookies, list):
                return cookies
            else:
                logger.error(f"Cookie JSON格式错误，期望列表，得到 {type(cookies)}")
                return None
        except Exception as e:
            logger.error(f"JSON解析为Cookie失败: {e}")
            return None


# 全局Cookie管理器实例
cookie_manager = CookieManager()