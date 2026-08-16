"""市场路由：浏览市场快照与单作品市场表现（只读）。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world
from app.models.world import World
from app.models.market import MarketSnapshot, ProjectMarket
from app.schemas.market import MarketSnapshotOut, ProjectMarketOut

router = APIRouter(prefix="/worlds/{world_id}/markets", tags=["市场"])


@router.get("/snapshots", response_model=list[MarketSnapshotOut])
def list_snapshots(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    skip: int = 0, limit: int = 200,
):
    return (
        db.query(MarketSnapshot).filter(MarketSnapshot.world_id == world.id)
        .order_by(MarketSnapshot.snapshot_date.desc()).offset(skip).limit(limit).all()
    )


@router.get("/projects/{project_id}", response_model=ProjectMarketOut)
def project_market(
    project_id: int = Path(..., description="作品 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    pm = db.query(ProjectMarket).filter(
        ProjectMarket.project_id == project_id, ProjectMarket.world_id == world.id).first()
    if not pm:
        raise HTTPException(status_code=404, detail="该作品尚无市场表现记录（可能未上映）")
    return pm
