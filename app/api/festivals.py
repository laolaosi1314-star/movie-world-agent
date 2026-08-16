"""电影节路由：浏览 / 创建电影节、届次与奖项；支持上帝模式手动设奖（可审计）。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Path
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world, require_permission
from app.models.world import World
from app.models.festival import Festival, FestivalEdition, FestivalAward
from app.models.misc import Intervention
from app.models.player import Player
from app.models.enums import InterventionType
from app.auth.roles import PERM_WORLD_INTERVENE
from app.schemas.festival import (
    FestivalCreate, FestivalOut, FestivalEditionOut, FestivalAwardOut, FestivalAwardSet,
)

router = APIRouter(prefix="/worlds/{world_id}/festivals", tags=["电影节"])


@router.get("", response_model=list[FestivalOut])
def list_festivals(world: World = Depends(get_world), db: Session = Depends(get_db)):
    return db.query(Festival).filter(Festival.world_id == world.id).order_by(Festival.id).all()


@router.post("", response_model=FestivalOut, status_code=http_status.HTTP_201_CREATED)
def create_festival(
    payload: FestivalCreate,
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    festival = Festival(
        world_id=world.id,
        name=payload.name,
        founded_year=payload.founded_year,
        location=payload.location,
        level=payload.level,
        positioning=payload.positioning,
        selection_rules=payload.selection_rules,
        jury=payload.jury,
        units=payload.units,
    )
    db.add(festival)
    db.commit()
    db.refresh(festival)
    return festival


@router.get("/{festival_id}/editions", response_model=list[FestivalEditionOut])
def list_editions(
    festival_id: int = Path(..., description="电影节 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    festival = db.query(Festival).filter(
        Festival.id == festival_id, Festival.world_id == world.id).first()
    if not festival:
        raise HTTPException(status_code=404, detail="Festival not found")
    return (
        db.query(FestivalEdition).filter(FestivalEdition.festival_id == festival_id)
        .order_by(FestivalEdition.year).all()
    )


@router.get("/{festival_id}/editions/{edition_id}/awards", response_model=list[FestivalAwardOut])
def list_awards(
    festival_id: int = Path(..., description="电影节 ID"),
    edition_id: int = Path(..., description="届次 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    return db.query(FestivalAward).filter(FestivalAward.edition_id == edition_id).all()


@router.post("/{festival_id}/editions/{edition_id}/awards/override",
             response_model=FestivalAwardOut, status_code=http_status.HTTP_201_CREATED)
def override_award(
    payload: FestivalAwardSet,
    festival_id: int = Path(..., description="电影节 ID"),
    edition_id: int = Path(..., description="届次 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_WORLD_INTERVENE)),
    db: Session = Depends(get_db),
):
    """上帝模式：手动设定某届某单元奖项。留痕到 interventions（可审计）。

    干预审计：Intervention.user_id 绑定发起此干预的 GM 玩家 id。
    """
    award = FestivalAward(
        edition_id=edition_id,
        category=payload.category,
        winner_project_id=payload.winner_project_id,
        winner_character_id=payload.winner_character_id,
        is_user_override=True,
    )
    db.add(award)
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="festival_award", target_id=edition_id,
        intervention_type=InterventionType.AWARD,
        field="category", old_value=None,
        new_value={"category": payload.category,
                   "winner_project_id": payload.winner_project_id,
                   "winner_character_id": payload.winner_character_id},
        reason=payload.reason or "上帝模式手动设定电影节奖项",
    ))
    db.commit()
    db.refresh(award)
    return award
