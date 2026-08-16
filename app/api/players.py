"""玩家身份路由（Phase 6 用户角色体系）。

无状态契约：所有接口均挂载在 `/worlds/{world_id}/players` 命名空间，
玩家身份由 `Authorization: Bearer <player_key>` 解析（见 app/api/deps.py）。
GM 角色创建受「自举/授权」边界约束：世界中首个 GM 可自由创建（自举），
其后任何 GM 创建必须由既有 GM 令牌授权。
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Path, Header
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_player, require_permission, _resolve_player
from app.models.world import World
from app.models.player import Player
from app.models.event import Event
from app.models.enums import PlayerRole, WorkDomain
from app.auth.roles import PERM_PLAYER_ADMIN, permissions_of, capabilities_of
from app.schemas.player import (
    PlayerCreate, PlayerOut, PlayerTokenOut, PlayerMeOut, PlayerPortalOut, PlayerCapability,
)
from app.schemas.event import EventOut

router = APIRouter(prefix="/worlds/{world_id}/players", tags=["玩家身份"])


@router.post("", response_model=PlayerTokenOut, status_code=status.HTTP_201_CREATED)
def create_player(
    world_id: int = Path(..., description="世界/存档 ID"),
    payload: PlayerCreate = ...,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """创建玩家并一次性下发 player_key（Bearer 令牌）。"""
    world = db.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=404, detail="World not found")

    # 角色合法性
    try:
        role = PlayerRole(payload.role)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"invalid role: {payload.role!r} "
                   f"(allowed: {[r.value for r in PlayerRole]})",
        )

    critic_domains = None
    if role == PlayerRole.CRITIC:
        if not payload.critic_domains:
            raise HTTPException(
                status_code=422,
                detail="critic 必须指定 critic_domains（WorkDomain 值列表，如 ['film','tv']）",
            )
        allowed = {e.value for e in WorkDomain}
        invalid = [d for d in payload.critic_domains if d not in allowed]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"invalid critic_domains: {invalid} (allowed: {sorted(allowed)})",
            )
        critic_domains = list(payload.critic_domains)

    # GM 自举 / 授权边界
    if role == PlayerRole.GM:
        existing_gm = (
            db.query(Player)
            .filter(Player.world_id == world_id, Player.role == PlayerRole.GM,
                    Player.is_active == True)  # noqa: E712
            .first()
        )
        if existing_gm is not None:
            actor = _resolve_player(world_id, authorization, db)
            if actor is None or actor.role != PlayerRole.GM:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="创建 GM 需由现有 GM 令牌授权",
                )

    player_key = secrets.token_hex(32)  # 64 位十六进制
    player = Player(
        world_id=world_id,
        name=payload.name,
        role=role,
        player_key=player_key,
        critic_domains=critic_domains,
        bio=payload.bio,
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return PlayerTokenOut(player=player, player_key=player_key)


@router.get("", response_model=list[PlayerOut])
def list_players(
    world_id: int = Path(..., description="世界/存档 ID"),
    db: Session = Depends(get_db),
):
    """列出本世界全部玩家（只读元数据）。"""
    return db.query(Player).filter(Player.world_id == world_id).order_by(Player.id).all()


def _build_me_out(player: Player) -> PlayerMeOut:
    """把 Player 实体装配为带能力集的 PlayerMeOut（供 /me 与 /portal 复用）。"""
    base = PlayerOut.model_validate(player).model_dump()
    actions = [PlayerCapability(**a) for a in capabilities_of(player.role)]
    return PlayerMeOut(
        **base,
        capabilities=sorted(permissions_of(player.role)),
        actions=actions,
    )


@router.get("/me", response_model=PlayerMeOut)
def whoami(player: Player = Depends(get_player)):
    """当前令牌对应的玩家身份 + 角色能力集（App/H5 用于渲染按钮 / 能力探测）。"""
    return _build_me_out(player)


@router.get("/me/portal", response_model=PlayerPortalOut)
def player_portal(
    world_id: int = Path(..., description="世界/存档 ID"),
    player: Player = Depends(get_player),
    db: Session = Depends(get_db),
):
    """面向 App/H5 首页的玩家视角聚合接口（单次调用即首页所需全部数据）。

    返回：玩家身份 + 能力集 + 世界快照 + 近期时间线（按角色可见性过滤）。
    无状态：所有数据均由 world_id + 令牌请求级解析，无任何会话态。
    """
    world = db.get(World, world_id)
    world_snapshot = {
        "id": world.id,
        "name": world.name,
        "current_year": world.current_year,
        "current_month": world.current_month,
        "industry_status": world.industry_status,
        "status": world.status.value if hasattr(world.status, "value") else world.status,
        "total_ticks": world.total_ticks,
    }
    # 近期时间线：玩家视角下默认可见本世界全部事件（GM 另含干预留痕，后续可细化可见性）。
    recent = (
        db.query(Event)
        .filter(Event.world_id == world_id)
        .order_by(Event.event_date.desc())
        .limit(20)
        .all()
    )
    return PlayerPortalOut(
        player=_build_me_out(player),
        world=world_snapshot,
        recent_events=[EventOut.model_validate(e) for e in recent],
    )


@router.get("/{player_id}", response_model=PlayerOut)
def get_player_info(
    world_id: int = Path(..., description="世界/存档 ID"),
    player_id: int = Path(..., description="玩家 ID"),
    db: Session = Depends(get_db),
):
    player = (
        db.query(Player)
        .filter(Player.world_id == world_id, Player.id == player_id)
        .first()
    )
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.post("/{player_id}/deactivate", response_model=PlayerOut)
def deactivate_player(
    world_id: int = Path(..., description="世界/存档 ID"),
    player_id: int = Path(..., description="玩家 ID"),
    db: Session = Depends(get_db),
    _gm: Player = Depends(require_permission(PERM_PLAYER_ADMIN)),
):
    """停用玩家（GM 专属）。"""
    player = (
        db.query(Player)
        .filter(Player.world_id == world_id, Player.id == player_id)
        .first()
    )
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    player.is_active = False
    db.commit()
    db.refresh(player)
    return player


@router.post("/{player_id}/activate", response_model=PlayerOut)
def activate_player(
    world_id: int = Path(..., description="世界/存档 ID"),
    player_id: int = Path(..., description="玩家 ID"),
    db: Session = Depends(get_db),
    _gm: Player = Depends(require_permission(PERM_PLAYER_ADMIN)),
):
    """重新启用玩家（GM 专属）。"""
    player = (
        db.query(Player)
        .filter(Player.world_id == world_id, Player.id == player_id)
        .first()
    )
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    player.is_active = True
    db.commit()
    db.refresh(player)
    return player
