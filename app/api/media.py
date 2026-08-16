"""媒体机构 API：列出 / 创建 / 微调媒体机构（含上帝模式干预）。"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_world_id, get_world, require_writable_world
from app.models.world import World
from app.models.media import MediaOutlet
from app.schemas.media import MediaOutletCreate, MediaOutletOut, MediaOutletUpdate
from app.models.enums import MediaOutletType, MediaStance

router = APIRouter(prefix="/worlds/{world_id}/media-outlets", tags=["media"])


@router.post("", response_model=MediaOutletOut, status_code=201)
def create_outlet(
    payload: MediaOutletCreate,
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    try:
        outlet_type = MediaOutletType(payload.outlet_type)
        stance = MediaStance(payload.stance)
    except ValueError:
        raise HTTPException(status_code=422, detail="outlet_type 或 stance 取值非法")
    outlet = MediaOutlet(
        world_id=world.id,
        name=payload.name,
        outlet_type=outlet_type,
        stance=stance,
        credibility=payload.credibility,
        preferred_categories=payload.preferred_categories,
        preferred_genres=payload.preferred_genres,
        founded_year=payload.founded_year or world.current_year,
    )
    db.add(outlet)
    db.commit()
    db.refresh(outlet)
    return outlet


@router.get("", response_model=List[MediaOutletOut])
def list_outlets(
    world_id: int = Depends(get_world_id),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    rows = (
        db.query(MediaOutlet)
        .filter(MediaOutlet.world_id == world_id)
        .order_by(MediaOutlet.id)
        .limit(limit)
        .all()
    )
    return rows


@router.patch("/{outlet_id}", response_model=MediaOutletOut)
def update_outlet(
    outlet_id: int,
    payload: MediaOutletUpdate,
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    outlet = (
        db.query(MediaOutlet)
        .filter(MediaOutlet.id == outlet_id, MediaOutlet.world_id == world.id)
        .first()
    )
    if not outlet:
        raise HTTPException(status_code=404, detail="媒体机构不存在")
    data = payload.model_dump(exclude_unset=True)
    if "stance" in data:
        try:
            data["stance"] = MediaStance(data["stance"])
        except ValueError:
            raise HTTPException(status_code=422, detail="stance 取值非法")
    for k, v in data.items():
        setattr(outlet, k, v)
    db.commit()
    db.refresh(outlet)
    return outlet
