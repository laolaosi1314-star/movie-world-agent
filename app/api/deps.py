"""API 依赖：world_id 注入 + 只读锁拦截 + 玩家身份解析（Phase 6 无状态鉴权）。

所有业务接口都通过以下依赖获取 world_id / World 对象 / Player 身份，
从而保证：
  1. 每个请求都显式携带 world_id（多存档隔离）；
  2. archived 世界的写操作被统一拒绝（423 Locked）；
  3. 玩家身份由 per-request 的 `Authorization: Bearer <player_key>` 解析（无会话状态），
     且 player.world_id 必须与路径 world_id 一致（跨世界操作被拒）。
"""
from typing import Optional
from fastapi import Depends, Path, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.world import World
from app.models.enums import WorldStatus
from app.models.player import Player
from app.auth.roles import WRITE_PERMISSIONS, role_has_permission


def get_world_id(world_id: int = Path(..., description="世界/存档 ID")) -> int:
    return world_id


def get_world(
    world_id: int = Depends(get_world_id),
    db: Session = Depends(get_db),
) -> World:
    world = db.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=404, detail="World not found")
    return world


def require_writable_world(world: World = Depends(get_world)) -> World:
    """写操作依赖：只读存档返回 423 Locked。"""
    if world.status == WorldStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="该存档为只读存档，不可修改（如需编辑请先克隆为新档）",
        )
    return world


# ===== Phase 6：玩家身份解析（无状态） =====
def _resolve_player(world_id: int, authorization: Optional[str], db: Session) -> Optional[Player]:
    """从 Bearer 头解析玩家；任一校验失败返回 None（视为未授权）。

    解析链：Bearer 方案 → player_key 查询 → 启用态 → world 作用域一致。
    """
    if not authorization:
        return None
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    player = db.query(Player).filter(Player.player_key == token).first()
    if player is None or not player.is_active:
        return None
    if player.world_id != world_id:
        # 令牌合法但属于其它世界 → 本世界视为未授权（跨世界隔离）。
        return None
    return player


def get_player_optional(
    world_id: int = Depends(get_world_id),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, description="Authorization: Bearer <player_key>"),
) -> Optional[Player]:
    """解析玩家身份（可选）；无令牌/无效令牌返回 None，供只读/匿名场景使用。"""
    return _resolve_player(world_id, authorization, db)


def get_player(
    world_id: int = Depends(get_world_id),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, description="Authorization: Bearer <player_key>"),
) -> Player:
    """解析玩家身份（必需）；缺失/无效令牌返回 401。"""
    player = _resolve_player(world_id, authorization, db)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或无效的玩家身份令牌（Authorization: Bearer <player_key>）",
        )
    return player


def require_permission(permission: str):
    """依赖工厂：解析玩家并校验其角色是否拥有 `permission`。

    - 写类权限（WRITE_PERMISSIONS）额外经 423 只读锁；
    - 无令牌 → 401；令牌角色无权 → 403。
    用法：`gm: Player = Depends(require_permission(PERM_PLAYER_ADMIN))`。
    """
    def _dep(
        world: World = Depends(get_world),
        player: Optional[Player] = Depends(get_player_optional),
    ) -> Player:
        if permission in WRITE_PERMISSIONS and world.status == WorldStatus.ARCHIVED:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="该存档为只读存档，不可执行此操作",
            )
        if player is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要玩家身份令牌（Authorization: Bearer <player_key>）",
            )
        if not role_has_permission(player.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"角色 {player.role.value} 无权执行 {permission}",
            )
        return player
    return _dep

