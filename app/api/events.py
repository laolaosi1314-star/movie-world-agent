"""事件路由：按世界浏览事件流。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world
from app.models.world import World
from app.models.event import Event
from app.schemas.event import EventOut

router = APIRouter(prefix="/worlds/{world_id}/events", tags=["事件"])


@router.get("", response_model=list[EventOut])
def list_events(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    level: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
):
    q = db.query(Event).filter(Event.world_id == world.id)
    if level:
        q = q.filter(Event.level == level)
    return q.order_by(Event.event_date.desc()).offset(skip).limit(limit).all()
