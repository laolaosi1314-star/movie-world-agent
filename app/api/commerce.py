"""§17.1 商业时尚与塌房违约金路由：代言签约/解约 · 杂志封面 · 商业概览。

权限：写操作经 commerce:manage 网关（GM/运营角色），并经 Intervention 审计留痕；
只读存档（archived）写操作返回 423 Locked（require_permission 内置）。
塌房违约金为系统自动结算（由 §17.3 CrisisAgent 在 COLLAPSED 时触发），不经此路由。
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Path, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world, require_permission
from app.models.world import World
from app.models.character import Character
from app.models.commerce import Endorsement, MagazineCover
from app.models.player import Player
from app.models.misc import Intervention
from app.models.enums import (
    EndorsementTier, ContractStatus, MagazineTier, InterventionType,
)
from app.auth.roles import PERM_COMMERCE_MANAGE
from app.schemas.commerce import (
    EndorsementCreate, EndorsementTerminate, EndorsementOut,
    MagazineCoverCreate, MagazineCoverOut, CommercialSummary,
)
from app.sim.commerce_agent import BRAND_CATALOG, MAGAZINE_CATALOG

router = APIRouter(prefix="/worlds/{world_id}/commerce", tags=["商业时尚与塌房违约金"])


# ===================== 代言 =====================
@router.get("/endorsements", response_model=list[EndorsementOut])
def list_endorsements(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    character_id: Optional[int] = Query(None, description="按人物过滤"),
    status: Optional[str] = Query(None, description="active/terminated/breached/expired"),
    skip: int = 0, limit: int = 100,
):
    """列出本世界代言合约（world:read）。"""
    q = db.query(Endorsement).filter(Endorsement.world_id == world.id)
    if character_id is not None:
        q = q.filter(Endorsement.character_id == character_id)
    if status:
        q = q.filter(Endorsement.status == status)
    return q.order_by(Endorsement.id).offset(skip).limit(limit).all()


@router.post("/endorsements", response_model=EndorsementOut,
             status_code=http_status.HTTP_201_CREATED)
def sign_endorsement(
    payload: EndorsementCreate,
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_COMMERCE_MANAGE)),
    db: Session = Depends(get_db),
):
    """GM/运营为某人物签下代言（commerce:manage 网关 + Intervention 审计）。

    品牌名留空时按 tier 从确定性目录择一；费用未填时按目录基准 × 人气估算。
    """
    character = db.query(Character).filter(
        Character.id == payload.character_id, Character.world_id == world.id).first()
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found")

    tier = payload.tier
    try:
        tier = EndorsementTier(payload.tier)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"未知 tier: {payload.tier}")

    brand = next((b for b in BRAND_CATALOG if b["name"] == payload.brand_name), None)
    if payload.brand_name is None:
        brand = next((b for b in BRAND_CATALOG if b["tier"] == tier), None)
    brand_name = payload.brand_name or (brand["name"] if brand else f"{tier.value} 品牌")
    category = payload.category or (brand["category"] if brand else None)
    heat = int((character.attributes or {}).get("heat", 50))
    annual_fee = payload.annual_fee or (
        int(round(brand["base_fee"] * (0.5 + heat / 100.0))) if brand else 0)
    penalty_rate = payload.penalty_rate
    if brand is not None and payload.penalty_rate == 0.5:
        penalty_rate = brand["penalty_rate"]

    signed_tick = payload.signed_tick if payload.signed_tick is not None else world.total_ticks
    rec = Endorsement(
        world_id=world.id, character_id=character.id,
        brand_name=brand_name, category=category, tier=tier,
        annual_fee=annual_fee, penalty_rate=penalty_rate,
        has_morals_clause=payload.has_morals_clause,
        signed_tick=signed_tick, duration_ticks=payload.duration_ticks,
        status=ContractStatus.ACTIVE,
    )
    db.add(rec)
    db.flush()
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="endorsement",
        target_id=rec.id, intervention_type=InterventionType.CREATE,
        field="status", old_value=None,
        new_value={"brand": brand_name, "tier": tier.value, "annual_fee": annual_fee,
                   "penalty_rate": float(penalty_rate),
                   "has_morals_clause": payload.has_morals_clause},
        reason="GM 签约代言",
    ))
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/endorsements/{endorsement_id}/terminate", response_model=EndorsementOut)
def terminate_endorsement(
    payload: EndorsementTerminate,
    endorsement_id: int = Path(..., description="代言 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_COMMERCE_MANAGE)),
    db: Session = Depends(get_db),
):
    """协商解约（terminated，无违约金）或标记违约（breached，已自动计赔则保留 penalty_amount）。"""
    rec = db.query(Endorsement).filter(
        Endorsement.id == endorsement_id, Endorsement.world_id == world.id).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="Endorsement not found")
    if rec.status != ContractStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="该代言已非生效状态")
    rec.status = ContractStatus.TERMINATED if payload.voluntary else ContractStatus.BREACHED
    rec.terminated_tick = world.total_ticks
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="endorsement",
        target_id=rec.id, intervention_type=InterventionType.STATUS,
        field="status", old_value="active",
        new_value=rec.status.value, reason=payload.note or "代言状态变更",
    ))
    db.commit()
    db.refresh(rec)
    return rec


# ===================== 杂志封面 =====================
@router.get("/covers", response_model=list[MagazineCoverOut])
def list_covers(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    character_id: Optional[int] = Query(None, description="按人物过滤"),
    status: Optional[str] = Query(None, description="active/terminated"),
    skip: int = 0, limit: int = 100,
):
    """列出本世界杂志封面（world:read）。"""
    q = db.query(MagazineCover).filter(MagazineCover.world_id == world.id)
    if character_id is not None:
        q = q.filter(MagazineCover.character_id == character_id)
    if status:
        q = q.filter(MagazineCover.status == status)
    return q.order_by(MagazineCover.id).offset(skip).limit(limit).all()


@router.post("/covers", response_model=MagazineCoverOut,
             status_code=http_status.HTTP_201_CREATED)
def create_cover(
    payload: MagazineCoverCreate,
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_COMMERCE_MANAGE)),
    db: Session = Depends(get_db),
):
    """GM/运营为某人物安排杂志封面（commerce:manage 网关 + Intervention 审计）。"""
    character = db.query(Character).filter(
        Character.id == payload.character_id, Character.world_id == world.id).first()
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        tier = MagazineTier(payload.tier)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"未知 tier: {payload.tier}")

    mag = next((m for m in MAGAZINE_CATALOG if m["name"] == payload.magazine_name), None)
    if payload.magazine_name is None:
        mag = next((m for m in MAGAZINE_CATALOG if m["tier"] == tier), None)
    magazine_name = payload.magazine_name or (mag["name"] if mag else f"{tier.value} 刊物")
    prestige = payload.prestige if mag is None else (payload.prestige or mag["prestige"])
    heat = int((character.attributes or {}).get("heat", 50))
    fee = payload.fee if payload.fee is not None else (
        int(round(mag["base_fee"] * (0.5 + heat / 100.0))) if mag else None)
    issue_tick = payload.issue_tick if payload.issue_tick is not None else world.total_ticks + 1

    rec = MagazineCover(
        world_id=world.id, character_id=character.id,
        magazine_name=magazine_name, tier=tier, issue_tick=issue_tick,
        theme=payload.theme or "封面人物", fee=fee, prestige=prestige,
        status=ContractStatus.ACTIVE,
    )
    db.add(rec)
    db.flush()
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="cover",
        target_id=rec.id, intervention_type=InterventionType.CREATE,
        field="status", old_value=None,
        new_value={"magazine": magazine_name, "tier": tier.value,
                   "issue_tick": issue_tick, "prestige": prestige},
        reason="GM 安排封面",
    ))
    db.commit()
    db.refresh(rec)
    return rec


# ===================== 人物商业概览 =====================
@router.get("/characters/{character_id}/summary", response_model=CommercialSummary)
def commercial_summary(
    character_id: int = Path(..., description="人物 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    """某人物的商业价值与合约概览（world:read）。"""
    character = db.query(Character).filter(
        Character.id == character_id, Character.world_id == world.id).first()
    if character is None:
        raise HTTPException(status_code=404, detail="Character not found")

    endorsements = db.query(Endorsement).filter(
        Endorsement.world_id == world.id, Endorsement.character_id == character_id).all()
    covers = db.query(MagazineCover).filter(
        MagazineCover.world_id == world.id,
        MagazineCover.character_id == character_id).all()

    active_e = [e for e in endorsements if e.status == ContractStatus.ACTIVE]
    breached_e = [e for e in endorsements if e.status == ContractStatus.BREACHED]
    active_c = [c for c in covers if c.status == ContractStatus.ACTIVE]
    cancelled_c = [c for c in covers if c.status == ContractStatus.TERMINATED]
    total_penalty = sum(int(e.penalty_amount or 0) for e in breached_e)

    return CommercialSummary(
        character_id=character_id,
        commercial_value=float(character.commercial_value)
        if character.commercial_value is not None else None,
        active_endorsements=len(active_e),
        breached_endorsements=len(breached_e),
        active_covers=len(active_c),
        cancelled_covers=len(cancelled_c),
        total_penalty_paid=total_penalty,
    )
