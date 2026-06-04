"""角色权限管理 —— RBAC 权限矩阵"""

from typing import List
from src.config.settings import ROLE_PERMISSIONS


class RoleManager:
    """角色权限管理器"""

    PERMISSIONS = ROLE_PERMISSIONS

    @classmethod
    def has_permission(cls, role: str, action: str) -> bool:
        """检查角色是否有指定权限
        Args:
            role: 角色名 (admin/commander/researcher/grassroots)
            action: 权限动作名
        Returns:
            True 如果有权限
        """
        if role not in cls.PERMISSIONS:
            return False
        return action in cls.PERMISSIONS[role]

    @classmethod
    def get_role_permissions(cls, role: str) -> List[str]:
        """获取角色的所有权限列表"""
        return cls.PERMISSIONS.get(role, [])

    @classmethod
    def get_all_roles(cls) -> List[str]:
        """获取所有可用角色"""
        return list(cls.PERMISSIONS.keys())
