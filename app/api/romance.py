"""§17.2 人际情感网络路由：关系编排(恋情/绯闻/婚育) · 粉丝蝴蝶效应 · 人生档案馆接口。

权限：
  - 关系创建/公开/结束/生子 经 relationship:manage 网关（GM/运营角色），并经 Intervention 审计留痕；
    只读存档（archived）写操作返回 423 Locked（require_permission 内置）。
  - 人生档案馆 GET /characters/{id}/archive 为只读聚合，仅需 world:read（任意已授权玩家可查）。
  - 与 §17.3 拆散、§17.1 商业贬值 的桥接在 RomanceAgent 内完成，媒体 Agent 零改动（复用 §14 闭环）。
"""
import datetime

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Path, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world, require_permission
from app.models.world import World, SimulationTick
from app.models.character import Character
from app.models.romance import Romance
from app.models.player import Player
from app.models.misc import Intervention
from app.models.enums import RomanceType, RomanceStatus, InterventionType
from app.auth.roles import PERM_RELATIONSHIP_MANAGE
from app.schemas.relationship import (
    RomanceCreate, RomanceReveal, RomanceEnd, RomanceAddChild, RomanceOut, LifeArchiveOut,
)
from app.sim.romance_agent import RomanceAgent, apply_romance_reaction
from app.sim.life_archive import build_archive

router = APIRouter(prefix="/worlds/{world_id}", tags=["人际情感网络与人生档案馆"])


def _fake_tick(world: World) -> SimulationTick:
    """非 tick 上下文（官宣/结束/生子）构造最小 SimulationTick 视图（tick_id=None，FK 可空）。"""
    y, m = world.current_year, world.current_month
    to_date = datetime.datetime(y, m, 1, tzinfo=datetime.timezone.utc)
    return SimulationTick(
        id=None, world_id=world.id, tick_index=world.total_ticks,
        unit="manual", from_date=to_date, to_date=to_date,
    )


# ===================== 情感关系 =====================
@router.get("/relationships", response_model=list[RomanceOut])
def list_romances(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    character_id: Optional[int] = Query(None, description="按人物过滤（a 或 b）"),
    status: Optional[str] = Query(None, description="active/ended"),
    skip: int = 0, limit: int = 100,
):
    """列出本世界情感关系（world:read）。"""
    q = db.query(Romance).filter(Romance.world_id == world.id)
    if character_id is not None:
        q = q.filter((Romance.character_a_id == character_id) |
                     (Romance.character_b_id == character_id))
    if status:
        q = q.filter(Romance.status == status)
    return q.order_by(Romance.id).offset(skip).limit(limit).all()


@router.post("/relationships", response_model=RomanceOut,
             status_code=http_status.HTTP_201_CREATED)
def create_romance(
    payload: RomanceCreate,
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_RELATIONSHIP_MANAGE)),
    db: Session = Depends(get_db),
):
    """GM/运营编排一段情感关系（relationship:manage 网关 + Intervention 审计）。"""
    if payload.character_a_id == payload.character_b_id:
        raise HTTPException(status_code=422, detail="不能与自己建立关系")
    for cid in (payload.character_a_id, payload.character_b_id):
        c = db.query(Character).filter(
            Character.id == cid, Character.world_id == world.id).first()
        if c is None:
            raise HTTPException(status_code=404, detail=f"Character {cid} not found")
    try:
        rtype = RomanceType(payload.romance_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"未知 romance_type: {payload.romance_type}")

    rec = Romance(
        world_id=world.id, character_a_id=payload.character_a_id,
        character_b_id=payload.character_b_id, romance_type=rtype,
        status=RomanceStatus.ACTIVE, is_public=payload.is_public,
        publicness=payload.publicness, child_count=payload.child_count,
        started_tick=world.total_ticks, created_by=str(player.id),
        notes=payload.notes,
    )
    db.add(rec)
    db.flush()
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="romance",
        target_id=rec.id, intervention_type=InterventionType.CREATE,
        field="status", old_value=None,
        new_value={"type": rtype.value, "is_public": payload.is_public,
                   "publicness": payload.publicness},
        reason="GM 编排情感关系",
    ))
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/relationships/{romance_id}/reveal", response_model=RomanceOut)
def reveal_romance(
    payload: RomanceReveal,
    romance_id: int = Path(..., description="关系 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_RELATIONSHIP_MANAGE)),
    db: Session = Depends(get_db),
):
    """主动官宣公开（若尚未结算过粉丝蝴蝶效应则即时结算）。"""
    rec = db.query(Romance).filter(
        Romance.id == romance_id, Romance.world_id == world.id).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="Romance not found")
    if rec.status != RomanceStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="该关系已结束")
    rec.is_public = True
    if rec.reacted_tick is None:
        tick = _fake_tick(world)
        apply_romance_reaction(db, world, tick, rec,
                                f"{rec.romance_type.value} 官宣公开")
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="romance",
        target_id=rec.id, intervention_type=InterventionType.STATUS,
        field="is_public", old_value=False, new_value=True,
        reason=payload.notes or "官宣公开",
    ))
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/relationships/{romance_id}/add-child", response_model=RomanceOut)
def add_child(
    payload: RomanceAddChild,
    romance_id: int = Path(..., description="关系 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_RELATIONSHIP_MANAGE)),
    db: Session = Depends(get_db),
):
    """增加子女数量（结婚/稳定关系后）；若已公开则触发「生子」粉丝反应。"""
    rec = db.query(Romance).filter(
        Romance.id == romance_id, Romance.world_id == world.id).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="Romance not found")
    if rec.status != RomanceStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="该关系已结束")
    rec.child_count = (rec.child_count or 0) + payload.count
    # 生子：已公开关系触发一次「新生儿」粉丝反应（确定性）
    if rec.is_public and rec.reacted_tick is not None:
        tick = _fake_tick(world)
        apply_romance_reaction(db, world, tick, rec, "喜得子女（公开）")
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="romance",
        target_id=rec.id, intervention_type=InterventionType.STATUS,
        field="child_count", old_value=rec.child_count - payload.count,
        new_value=rec.child_count, reason=payload.notes or "新增子女",
    ))
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/relationships/{romance_id}/end", response_model=RomanceOut)
def end_romance(
    payload: RomanceEnd,
    romance_id: int = Path(..., description="关系 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_RELATIONSHIP_MANAGE)),
    db: Session = Depends(get_db),
):
    """结束情感关系（分手/离婚）。"""
    rec = db.query(Romance).filter(
        Romance.id == romance_id, Romance.world_id == world.id).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="Romance not found")
    if rec.status != RomanceStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="该关系已结束")
    rec.status = RomanceStatus.ENDED
    rec.ended_tick = world.total_ticks
    rec.ended_reason = payload.reason or "分手/离婚"
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="romance",
        target_id=rec.id, intervention_type=InterventionType.STATUS,
        field="status", old_value="active", new_value="ended",
        reason=payload.reason or "结束关系",
    ))
    db.commit()
    db.refresh(rec)
    return rec


# ===================== 人生档案馆（只读聚合） =====================
@router.get("/characters/{character_id}/archive", response_model=LifeArchiveOut)
def life_archive(
    character_id: int = Path(..., description="人物 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    """某人物的一生档案与时间轴（world:read，只读聚合，无写权限要求）。

    结构化呈现历年奖项、代言/封面、丑闻、情感变迁与重大事件；
    legacy_footnotes 读取长期记忆，随岁月沉淀动态渲染（如塌房后自动带出注脚）。
    """
    character = db.query(Character).filter(
        Character.id == character_id, Character.world_id == world.id).first()
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return build_archive(db, world, character)
