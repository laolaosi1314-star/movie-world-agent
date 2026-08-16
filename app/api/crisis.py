"""§17.3 舆论与危机公关路由：黑料爆料 / 曝光 / 多阶段公关（含 world_id 隔离与只读锁）。

权限：所有写操作经 crisis:manage 网关（GM/运营角色），并经 Intervention 审计留痕；
只读存档（archived）写操作返回 423 Locked（require_permission 内置）。
"""
from typing import Optional
import datetime as _dt
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Path, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world, require_permission
from app.models.world import World
from app.models.character import Character
from app.models.crisis import Scandal, CrisisPR
from app.models.player import Player
from app.models.misc import Intervention
from app.models.enums import ScandalType, ScandalStage, PRStrategy, InterventionType
from app.auth.roles import PERM_CRISIS_MANAGE
from app.schemas.crisis import (
    ScandalCreate, ScandalExpose, PRStrategyIn, ScandalOut, CrisisPROut,
)
from app.sim.crisis_agent import CrisisAgent

router = APIRouter(prefix="/worlds/{world_id}/scandals", tags=["舆论与危机公关"])


@router.get("", response_model=list[ScandalOut])
def list_scandals(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    stage: Optional[str] = Query(None, description="按阶段过滤（latent/spreading/erupted/resolving/resolved/collapsed）"),
    character_id: Optional[int] = Query(None, description="按人物过滤"),
    skip: int = 0,
    limit: int = 100,
):
    """列出本世界丑闻（world:read）。"""
    q = db.query(Scandal).filter(Scandal.world_id == world.id)
    if stage:
        q = q.filter(Scandal.stage == stage)
    if character_id is not None:
        q = q.filter(Scandal.character_id == character_id)
    return q.order_by(Scandal.id).offset(skip).limit(limit).all()


@router.post("", response_model=ScandalOut, status_code=http_status.HTTP_201_CREATED)
def create_scandal(
    payload: ScandalCreate,
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_CRISIS_MANAGE)),
    db: Session = Depends(get_db),
):
    """黑料爆料：创建一条丑闻（立即曝光或先潜伏），受 crisis:manage 网关约束，留痕 Intervention。"""
    character = db.query(Character).filter(
        Character.id == payload.character_id, Character.world_id == world.id).first()
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        s_type = ScandalType(payload.scandal_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"未知 scandal_type: {payload.scandal_type}")

    initial_heat = 45 + payload.severity * 2 if payload.exposed else 5
    stage = ScandalStage.SPREADING if payload.exposed else ScandalStage.LATENT
    scandal = Scandal(
        world_id=world.id, character_id=character.id,
        related_project_id=payload.related_project_id,
        scandal_type=s_type, title=payload.title,
        severity=payload.severity, evidence_strength=payload.evidence_strength,
        is_confirmed=payload.is_confirmed, stage=stage,
        heat=min(100, initial_heat), public_opinion=50,
        exposed_tick=world.total_ticks if payload.exposed else None,
        created_by=str(player.id), notes=payload.notes,
    )
    db.add(scandal)
    db.flush()
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="scandal",
        target_id=scandal.id, intervention_type=InterventionType.SCANDAL,
        field="stage", old_value=None,
        new_value={"title": payload.title, "scandal_type": s_type.value,
                   "severity": payload.severity,
                   "evidence_strength": payload.evidence_strength,
                   "is_confirmed": payload.is_confirmed, "exposed": payload.exposed,
                   "initial_stage": stage.value},
        reason=payload.notes or "黑料爆料",
    ))
    db.commit()
    db.refresh(scandal)
    return scandal


@router.get("/{scandal_id}", response_model=ScandalOut)
def get_scandal(
    scandal_id: int = Path(..., description="丑闻 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    scandal = db.query(Scandal).filter(
        Scandal.id == scandal_id, Scandal.world_id == world.id).first()
    if scandal is None:
        raise HTTPException(status_code=404, detail="Scandal not found")
    return scandal


@router.post("/{scandal_id}/expose", response_model=ScandalOut,
             status_code=http_status.HTTP_200_OK)
def expose_scandal(
    payload: ScandalExpose,
    scandal_id: int = Path(..., description="丑闻 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_CRISIS_MANAGE)),
    db: Session = Depends(get_db),
):
    """曝光一条潜伏(LATENT)丑闻，使其进入 SPREADING（发酵），留痕 Intervention。"""
    scandal = db.query(Scandal).filter(
        Scandal.id == scandal_id, Scandal.world_id == world.id).first()
    if scandal is None:
        raise HTTPException(status_code=404, detail="Scandal not found")
    if scandal.stage != ScandalStage.LATENT:
        raise HTTPException(status_code=409, detail="该丑闻已非潜伏状态，无法重复曝光")
    scandal.stage = ScandalStage.SPREADING
    scandal.exposed_tick = world.total_ticks
    scandal.heat = max(scandal.heat, 45 + scandal.severity * 2)
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="scandal",
        target_id=scandal.id, intervention_type=InterventionType.SCANDAL,
        field="stage", old_value="latent", new_value="spreading",
        reason=payload.notes or "曝光潜伏丑闻",
    ))
    db.commit()
    db.refresh(scandal)
    return scandal


@router.post("/{scandal_id}/pr", response_model=CrisisPROut,
             status_code=http_status.HTTP_201_CREATED)
def launch_pr(
    payload: PRStrategyIn,
    scandal_id: int = Path(..., description="丑闻 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_CRISIS_MANAGE)),
    db: Session = Depends(get_db),
):
    """多阶段公关：发起一次公关动作（冷处理/律师函/道歉/买热搜/洗白反转）。

    由 CrisisAgent 以确定性舆论恢复曲线结算，经 Intervention(crisis_pr) 审计留痕。
    已塌房/平息的丑闻公关无效但同样留痕。
    """
    scandal = db.query(Scandal).filter(
        Scandal.id == scandal_id, Scandal.world_id == world.id).first()
    if scandal is None:
        raise HTTPException(status_code=404, detail="Scandal not found")
    try:
        strategy = PRStrategy(payload.strategy)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"未知 strategy: {payload.strategy}")

    agent = CrisisAgent(db, world, _fake_tick(world))
    rec = agent.apply_pr(scandal, strategy, str(player.id), payload.note)
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="scandal",
        target_id=scandal.id, intervention_type=InterventionType.CRISIS_PR,
        field="strategy", old_value=scandal.stage.value,
        new_value={"strategy": strategy.value, "impact": rec.impact,
                   "new_stage": scandal.stage.value,
                   "new_heat": scandal.heat, "new_opinion": scandal.public_opinion},
        reason=payload.note or f"公关：{strategy.value}",
    ))
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/{scandal_id}/pr", response_model=list[CrisisPROut])
def list_pr_history(
    scandal_id: int = Path(..., description="丑闻 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    """查询某丑闻的公关动作历史（world:read）。"""
    scandal = db.query(Scandal).filter(
        Scandal.id == scandal_id, Scandal.world_id == world.id).first()
    if scandal is None:
        raise HTTPException(status_code=404, detail="Scandal not found")
    return (
        db.query(CrisisPR).filter(CrisisPR.scandal_id == scandal_id)
        .order_by(CrisisPR.id).all()
    )


def _fake_tick(world: World):
    """公关动作在非 tick 上下文发起，构造一个最小 SimulationTick 视图供 CrisisAgent 写入事件。

    CrisisAgent 仅用到 tick.id / tick.tick_index / tick.to_date；此处 id=None（事件不挂接
    具体模拟 tick，作为玩家干预的历史记录落库），tick_index 取世界当前总 tick，保证事件可落库
    且危机数值变化会在后续 sim/advance 的演化中继续经 §14 媒体闭环发酵。
    """
    from app.models.world import SimulationTick
    base = _dt.datetime(world.current_year, world.current_month, 1,
                        tzinfo=_dt.timezone.utc)
    return SimulationTick(
        id=None, world_id=world.id,
        tick_index=world.total_ticks,
        unit="pr", from_date=base, to_date=base, rng_seed_used=world.rng_seed,
    )
