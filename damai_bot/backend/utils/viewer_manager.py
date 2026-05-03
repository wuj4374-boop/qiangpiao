#!/usr/bin/env python3
"""
观演人管理模块
用于管理大麦观演人信息（姓名、身份证、手机号）
支持选择1-3个观演人，并保存选择
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ViewerInfo:
    """观演人信息"""
    name: str           # 姓名
    id_card: str        # 身份证号码
    phone: str          # 手机号
    viewer_id: str      # 观演人ID（大麦系统内的ID）
    is_default: bool = False  # 是否为默认观演人

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ViewerInfo':
        """从字典创建"""
        return cls(
            name=data.get('name', ''),
            id_card=data.get('id_card', ''),
            phone=data.get('phone', ''),
            viewer_id=data.get('viewer_id', ''),
            is_default=data.get('is_default', False)
        )

    def validate(self) -> bool:
        """验证观演人信息是否有效"""
        if not self.name or not self.name.strip():
            return False

        # 简单验证身份证格式（15或18位）
        id_card = self.id_card.strip()
        if len(id_card) not in (15, 18):
            return False

        # 简单验证手机号格式（11位数字）
        phone = self.phone.strip()
        if len(phone) != 11 or not phone.isdigit():
            return False

        return True


class ViewerManager:
    """观演人管理器"""

    def __init__(self, config_dir: str = "config"):
        """
        初始化观演人管理器

        Args:
            config_dir: 配置目录路径
        """
        self.config_dir = config_dir
        self.viewers_file = os.path.join(config_dir, "viewers.json")
        self.selected_file = os.path.join(config_dir, "selected_viewers.json")

        # 确保配置目录存在
        os.makedirs(config_dir, exist_ok=True)

        # 观演人列表
        self.viewers: List[ViewerInfo] = []

        # 已选择的观演人ID集合（最多3个）
        self.selected_viewer_ids: Set[str] = set()

        # 加载数据
        self.load_viewers()
        self.load_selected()

    def load_viewers(self) -> bool:
        """
        加载观演人列表

        Returns:
            bool: 是否加载成功
        """
        try:
            if os.path.exists(self.viewers_file):
                with open(self.viewers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                viewers_data = data.get('viewers', [])
                self.viewers = [ViewerInfo.from_dict(viewer) for viewer in viewers_data]

                logger.info(f"已加载 {len(self.viewers)} 个观演人")
                return True
            else:
                logger.info("观演人文件不存在，将使用空列表")
                self.viewers = []
                return True

        except Exception as e:
            logger.error(f"加载观演人列表失败: {e}")
            self.viewers = []
            return False

    def save_viewers(self) -> bool:
        """
        保存观演人列表

        Returns:
            bool: 是否保存成功
        """
        try:
            data = {
                'saved_at': datetime.now().isoformat(),
                'viewers': [viewer.to_dict() for viewer in self.viewers]
            }

            with open(self.viewers_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"已保存 {len(self.viewers)} 个观演人到 {self.viewers_file}")
            return True

        except Exception as e:
            logger.error(f"保存观演人列表失败: {e}")
            return False

    def load_selected(self) -> bool:
        """
        加载已选择的观演人

        Returns:
            bool: 是否加载成功
        """
        try:
            if os.path.exists(self.selected_file):
                with open(self.selected_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                selected_ids = data.get('selected_viewer_ids', [])
                self.selected_viewer_ids = set(selected_ids)

                # 验证选择的观演人是否存在
                valid_ids = set()
                for viewer_id in self.selected_viewer_ids:
                    if self.get_viewer_by_id(viewer_id):
                        valid_ids.add(viewer_id)
                    else:
                        logger.warning(f"选择的观演人ID不存在: {viewer_id}")

                self.selected_viewer_ids = valid_ids

                logger.info(f"已加载 {len(self.selected_viewer_ids)} 个已选择的观演人")
                return True
            else:
                logger.info("已选择观演人文件不存在，将使用空集合")
                self.selected_viewer_ids = set()
                return True

        except Exception as e:
            logger.error(f"加载已选择观演人失败: {e}")
            self.selected_viewer_ids = set()
            return False

    def save_selected(self) -> bool:
        """
        保存已选择的观演人

        Returns:
            bool: 是否保存成功
        """
        try:
            data = {
                'saved_at': datetime.now().isoformat(),
                'selected_viewer_ids': list(self.selected_viewer_ids)
            }

            with open(self.selected_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"已保存 {len(self.selected_viewer_ids)} 个已选择的观演人")
            return True

        except Exception as e:
            logger.error(f"保存已选择观演人失败: {e}")
            return False

    def get_viewer_by_id(self, viewer_id: str) -> Optional[ViewerInfo]:
        """
        根据ID获取观演人

        Args:
            viewer_id: 观演人ID

        Returns:
            ViewerInfo or None: 找到的观演人信息，未找到返回None
        """
        for viewer in self.viewers:
            if viewer.viewer_id == viewer_id:
                return viewer
        return None

    def get_all_viewers(self) -> List[ViewerInfo]:
        """
        获取所有观演人

        Returns:
            List[ViewerInfo]: 观演人列表
        """
        return self.viewers.copy()

    def get_selected_viewers(self) -> List[ViewerInfo]:
        """
        获取已选择的观演人

        Returns:
            List[ViewerInfo]: 已选择的观演人列表
        """
        selected = []
        for viewer_id in self.selected_viewer_ids:
            viewer = self.get_viewer_by_id(viewer_id)
            if viewer:
                selected.append(viewer)
        return selected

    def select_viewer(self, viewer_id: str) -> bool:
        """
        选择观演人

        Args:
            viewer_id: 要选择的观演人ID

        Returns:
            bool: 是否选择成功
        """
        # 检查观演人是否存在
        viewer = self.get_viewer_by_id(viewer_id)
        if not viewer:
            logger.warning(f"尝试选择不存在的观演人: {viewer_id}")
            return False

        # 检查是否已达到最大选择数量（3个）
        if len(self.selected_viewer_ids) >= 3:
            logger.warning("已达到最大选择数量（3个），无法选择更多观演人")
            return False

        # 添加选择
        self.selected_viewer_ids.add(viewer_id)
        logger.info(f"已选择观演人: {viewer.name} (ID: {viewer_id})")

        # 保存选择
        self.save_selected()
        return True

    def deselect_viewer(self, viewer_id: str) -> bool:
        """
        取消选择观演人

        Args:
            viewer_id: 要取消选择的观演人ID

        Returns:
            bool: 是否取消选择成功
        """
        if viewer_id in self.selected_viewer_ids:
            self.selected_viewer_ids.remove(viewer_id)

            viewer = self.get_viewer_by_id(viewer_id)
            if viewer:
                logger.info(f"已取消选择观演人: {viewer.name} (ID: {viewer_id})")

            # 保存选择
            self.save_selected()
            return True

        logger.warning(f"尝试取消选择未选择的观演人: {viewer_id}")
        return False

    def clear_selected(self) -> bool:
        """
        清空所有选择

        Returns:
            bool: 是否清空成功
        """
        self.selected_viewer_ids.clear()
        logger.info("已清空所有观演人选择")

        # 保存选择
        self.save_selected()
        return True

    def set_selected_viewers(self, viewer_ids: List[str]) -> bool:
        """
        设置选择的观演人（批量）

        Args:
            viewer_ids: 要选择的观演人ID列表（最多3个）

        Returns:
            bool: 是否设置成功
        """
        # 验证数量
        if len(viewer_ids) > 3:
            logger.warning(f"选择数量 {len(viewer_ids)} 超过最大限制（3个）")
            return False

        # 验证所有观演人是否存在
        for viewer_id in viewer_ids:
            if not self.get_viewer_by_id(viewer_id):
                logger.warning(f"观演人不存在: {viewer_id}")
                return False

        # 更新选择
        self.selected_viewer_ids = set(viewer_ids)
        logger.info(f"已设置 {len(viewer_ids)} 个观演人选择")

        # 保存选择
        self.save_selected()
        return True

    def add_viewer(self, viewer: ViewerInfo) -> bool:
        """
        添加观演人

        Args:
            viewer: 要添加的观演人信息

        Returns:
            bool: 是否添加成功
        """
        # 验证观演人信息
        if not viewer.validate():
            logger.warning(f"观演人信息无效: {viewer.name}")
            return False

        # 检查是否已存在相同ID的观演人
        if viewer.viewer_id:
            existing = self.get_viewer_by_id(viewer.viewer_id)
            if existing:
                logger.warning(f"已存在相同ID的观演人: {viewer.viewer_id}")
                return False

        # 添加观演人
        self.viewers.append(viewer)
        logger.info(f"已添加观演人: {viewer.name}")

        # 保存到文件
        self.save_viewers()
        return True

    def update_viewer(self, viewer_id: str, updated_viewer: ViewerInfo) -> bool:
        """
        更新观演人信息

        Args:
            viewer_id: 要更新的观演人ID
            updated_viewer: 更新后的观演人信息

        Returns:
            bool: 是否更新成功
        """
        # 查找观演人
        for i, viewer in enumerate(self.viewers):
            if viewer.viewer_id == viewer_id:
                # 验证更新后的信息
                if not updated_viewer.validate():
                    logger.warning(f"更新后的观演人信息无效: {updated_viewer.name}")
                    return False

                # 更新观演人
                self.viewers[i] = updated_viewer
                logger.info(f"已更新观演人: {updated_viewer.name} (ID: {viewer_id})")

                # 保存到文件
                self.save_viewers()
                return True

        logger.warning(f"未找到要更新的观演人: {viewer_id}")
        return False

    def remove_viewer(self, viewer_id: str) -> bool:
        """
        删除观演人

        Args:
            viewer_id: 要删除的观演人ID

        Returns:
            bool: 是否删除成功
        """
        # 查找观演人
        for i, viewer in enumerate(self.viewers):
            if viewer.viewer_id == viewer_id:
                # 从选择中移除
                if viewer_id in self.selected_viewer_ids:
                    self.selected_viewer_ids.remove(viewer_id)
                    self.save_selected()

                # 删除观演人
                removed_viewer = self.viewers.pop(i)
                logger.info(f"已删除观演人: {removed_viewer.name} (ID: {viewer_id})")

                # 保存到文件
                self.save_viewers()
                return True

        logger.warning(f"未找到要删除的观演人: {viewer_id}")
        return False

    def get_selection_count(self) -> int:
        """
        获取已选择的观演人数量

        Returns:
            int: 已选择的观演人数量
        """
        return len(self.selected_viewer_ids)

    def can_select_more(self) -> bool:
        """
        检查是否可以选择更多观演人

        Returns:
            bool: 是否可以选择更多（未达到3个限制）
        """
        return len(self.selected_viewer_ids) < 3

    def fetch_viewers_from_damai(self) -> bool:
        """
        从大麦网获取观演人列表（需要登录）

        Returns:
            bool: 是否获取成功
        """
        logger.info("开始从大麦网获取观演人列表...")

        # 这里需要实现从大麦API获取观演人列表的逻辑
        # 由于大麦API可能变化，这里先返回模拟数据

        # 模拟数据（实际使用时需要替换为真实API调用）
        mock_viewers = [
            ViewerInfo(
                name="张三",
                id_card="110101199001011234",
                phone="13800138000",
                viewer_id="viewer_001",
                is_default=True
            ),
            ViewerInfo(
                name="李四",
                id_card="110101199002022345",
                phone="13800138001",
                viewer_id="viewer_002",
                is_default=False
            ),
            ViewerInfo(
                name="王五",
                id_card="110101199003033456",
                phone="13800138002",
                viewer_id="viewer_003",
                is_default=False
            ),
            ViewerInfo(
                name="赵六",
                id_card="110101199004044567",
                phone="13800138003",
                viewer_id="viewer_004",
                is_default=False
            )
        ]

        # 更新观演人列表
        self.viewers = mock_viewers

        # 保存到文件
        success = self.save_viewers()

        if success:
            logger.info(f"已从大麦网获取 {len(self.viewers)} 个观演人")
        else:
            logger.error("获取观演人列表成功，但保存到文件失败")

        return success

    def import_viewers_from_file(self, file_path: str) -> bool:
        """
        从文件导入观演人列表

        Args:
            file_path: 文件路径（JSON格式）

        Returns:
            bool: 是否导入成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            viewers_data = data.get('viewers', [])
            imported_viewers = []

            for viewer_data in viewers_data:
                viewer = ViewerInfo.from_dict(viewer_data)
                if viewer.validate():
                    imported_viewers.append(viewer)
                else:
                    logger.warning(f"跳过无效的观演人数据: {viewer_data.get('name', '未知')}")

            # 添加到现有列表（避免重复）
            for viewer in imported_viewers:
                # 检查是否已存在相同ID的观演人
                if not self.get_viewer_by_id(viewer.viewer_id):
                    self.viewers.append(viewer)

            # 保存到文件
            success = self.save_viewers()

            if success:
                logger.info(f"已从文件导入 {len(imported_viewers)} 个观演人")
            else:
                logger.error("导入观演人成功，但保存到文件失败")

            return success

        except Exception as e:
            logger.error(f"导入观演人文件失败: {e}")
            return False


# 全局实例
viewer_manager = ViewerManager()


# 同步包装函数（用于在非异步环境中调用）
def sync_get_all_viewers() -> List[Dict[str, Any]]:
    """同步版本：获取所有观演人"""
    viewers = viewer_manager.get_all_viewers()
    return [viewer.to_dict() for viewer in viewers]

def sync_get_selected_viewers() -> List[Dict[str, Any]]:
    """同步版本：获取已选择的观演人"""
    viewers = viewer_manager.get_selected_viewers()
    return [viewer.to_dict() for viewer in viewers]

def sync_select_viewer(viewer_id: str) -> bool:
    """同步版本：选择观演人"""
    return viewer_manager.select_viewer(viewer_id)

def sync_deselect_viewer(viewer_id: str) -> bool:
    """同步版本：取消选择观演人"""
    return viewer_manager.deselect_viewer(viewer_id)

def sync_set_selected_viewers(viewer_ids: List[str]) -> bool:
    """同步版本：设置选择的观演人"""
    return viewer_manager.set_selected_viewers(viewer_ids)

def sync_clear_selected() -> bool:
    """同步版本：清空所有选择"""
    return viewer_manager.clear_selected()

def sync_fetch_viewers_from_damai() -> bool:
    """同步版本：从大麦网获取观演人列表"""
    return viewer_manager.fetch_viewers_from_damai()

def sync_get_selection_count() -> int:
    """同步版本：获取已选择的观演人数量"""
    return viewer_manager.get_selection_count()

def sync_can_select_more() -> bool:
    """同步版本：检查是否可以选择更多观演人"""
    return viewer_manager.can_select_more()


if __name__ == "__main__":
    # 测试代码
    import sys

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建管理器实例
    manager = ViewerManager()

    print("=" * 50)
    print("观演人管理器测试")
    print("=" * 50)

    # 1. 获取观演人列表
    viewers = manager.get_all_viewers()
    print(f"1. 现有观演人数量: {len(viewers)}")

    if not viewers:
        print("  未找到观演人，从大麦网获取...")
        success = manager.fetch_viewers_from_damai()
        if success:
            viewers = manager.get_all_viewers()
            print(f"  已获取 {len(viewers)} 个观演人")

    # 2. 显示观演人信息
    for i, viewer in enumerate(viewers, 1):
        print(f"  观演人{i}: {viewer.name} | 身份证: {viewer.id_card} | 手机: {viewer.phone}")

    # 3. 选择观演人
    if viewers:
        print(f"\n2. 选择观演人 (最多3个)...")

        # 选择前两个观演人
        for viewer in viewers[:2]:
            success = manager.select_viewer(viewer.viewer_id)
            if success:
                print(f"  已选择: {viewer.name}")
            else:
                print(f"  选择失败: {viewer.name}")

    # 4. 获取已选择的观演人
    selected = manager.get_selected_viewers()
    print(f"\n3. 已选择的观演人: {len(selected)} 个")
    for viewer in selected:
        print(f"  - {viewer.name} (ID: {viewer.viewer_id})")

    # 5. 检查选择状态
    print(f"\n4. 选择状态:")
    print(f"  已选择数量: {manager.get_selection_count()}")
    print(f"  还可以选择: {3 - manager.get_selection_count()} 个")
    print(f"  是否可以选择更多: {manager.can_select_more()}")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)