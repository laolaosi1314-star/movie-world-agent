"""多世界管理（MW）路由：列出 / 创建 / 概览 / 转只读存档 / 克隆。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world
from app.models.world import World
from app.models.enums import WorldStatus
from app.schemas.world import WorldCreate, WorldOut

router = APIRouter(prefix="/worlds", tags=["多世界管理"])


@router.get("", response_model=list[WorldOut])
def list_worlds(db: Session = Depends(get_db)):
    """列出所有存档（含状态/年份）。"""
    return db.query(World).order_by(World.id).all()


@router.post("", response_model=WorldOut, status_code=status.HTTP_201_CREATED)
def create_world(payload: WorldCreate, db: Session = Depends(get_db)):
    """开新档（不删除任何旧档）。"""
    world = World(
        name=payload.name,
        description=payload.description,
        seed_config=payload.seed_config or {},
    )
    db.add(world)
    db.commit()
    db.refresh(world)
    return world


@router.get("/{world_id}", response_model=WorldOut)
def get_world_info(world: World = Depends(get_world)):
    return world


@router.post("/{world_id}/archive", response_model=WorldOut)
def archive_world(
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    """转为只读存档：active -> archived。"""
    world.status = WorldStatus.ARCHIVED
    db.commit()
    db.refresh(world)
    return world


@router.post("/{world_id}/clone", response_model=WorldOut, status_code=status.HTTP_201_CREATED)
def clone_world(world: World = Depends(get_world), db: Session = Depends(get_db)):
    """复制为新档（当前仅复制世界元信息；实体深拷贝为后续增强，见 CAD 蓝图）。"""
    new_world = World(
        name=f"{world.name} (副本)",
        current_year=world.current_year,
        current_month=world.current_month,
        industry_status=world.industry_status,
        rng_seed=world.rng_seed,
        description=world.description,
        seed_config=world.seed_config,
    )
    db.add(new_world)
    db.commit()
    db.refresh(new_world)
    return new_world
