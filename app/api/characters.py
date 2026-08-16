"""人物路由：列出 / 创建（含 world_id 过滤与只读锁）。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world
from app.models.world import World
from app.models.character import Character
from app.schemas.character import CharacterCreate, CharacterOut

router = APIRouter(prefix="/worlds/{world_id}/characters", tags=["人物"])


@router.get("", response_model=list[CharacterOut])
def list_characters(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    return (
        db.query(Character)
        .filter(Character.world_id == world.id)
        .order_by(Character.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("", response_model=CharacterOut, status_code=http_status.HTTP_201_CREATED)
def create_character(
    payload: CharacterCreate,
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    character = Character(
        world_id=world.id,
        type=payload.type,
        name=payload.name,
        birth_year=payload.birth_year,
        nationality=payload.nationality,
        career_stage=payload.career_stage,
        attributes=payload.attributes or {},
    )
    db.add(character)
    db.commit()
    db.refresh(character)
    return character
