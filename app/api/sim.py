"""时间推进（Tick）路由。"""
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world, require_permission
from app.models.world import World
from app.models.player import Player
from app.models.enums import PlayerRole
from app.auth.roles import PERM_SIM_ADVANCE
from app.schemas.event import AdvanceRequest, TickOut
from app.sim.engine import advance_world

router = APIRouter(prefix="/worlds/{world_id}/sim", tags=["时间推进"])


@router.post("/advance", response_model=TickOut)
def advance(
    payload: AdvanceRequest,
    world: World = Depends(require_writable_world),
    _player: Player = Depends(require_permission(PERM_SIM_ADVANCE)),
    db: Session = Depends(get_db),
):
    """推进模拟 tick。

    无状态鉴权：仅本世界已认证的玩家可推进（任何角色均拥有 sim:advance），
    只读存档经 require_writable_world 返回 423。玩家的 tick 动作本身不写入 interventions
    （属正常游玩，非上帝干预）；如需审计某次推进可后续扩展。
    """
    try:
        tick = advance_world(db, world, payload.unit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return tick
