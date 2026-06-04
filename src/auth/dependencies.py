"""FastAPI 认证与授权依赖注入"""

from typing import Optional
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.auth.jwt_handler import JWTHandler
from src.auth.role_manager import RoleManager

security = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    """当前用户上下文"""
    username: str
    role: str
    is_authenticated: bool = True


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser:
    """从 Authorization header 解析当前用户。
    未提供 Token 时返回未认证用户（用于公开端点可选注入）。
    提供但无效/过期 Token 时抛出 401。
    """
    if credentials is None:
        return CurrentUser(username="anonymous", role="anonymous", is_authenticated=False)

    token = credentials.credentials
    payload = JWTHandler.decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "message": "Token 无效或已过期", "data": None},
        )

    return CurrentUser(
        username=payload.get("sub", "unknown"),
        role=payload.get("role", "anonymous"),
        is_authenticated=True,
    )


def require_auth():
    """要求用户已认证（任意角色），否则返回 401。
    用法: Depends(require_auth)
    """
    async def _require_auth(user: CurrentUser = Depends(get_current_user)):
        if not user.is_authenticated:
            raise HTTPException(
                status_code=401,
                detail={"code": 401, "message": "请先登录", "data": None},
            )
        return user
    return _require_auth


def require_role(action: str):
    """要求当前用户具有指定权限，否则返回 403。
    用法: Depends(require_role("create_warning"))

    Args:
        action: 权限动作名 (如 'submit_data', 'create_warning')
    """
    async def _require_role(user: CurrentUser = Depends(require_auth())):
        if not RoleManager.has_permission(user.role, action):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": 403,
                    "message": f"权限不足，角色 '{user.role}' 没有 '{action}' 权限",
                    "data": None,
                },
            )
        return user
    return _require_role
