"""事件 / 时间推进相关 Schema。"""
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    tick_id: Optional[int] = None
    event_date: date
    level: str
    category: Optional[str] = None
    title: str
    description: Optional[str] = None
    causal_chain: Optional[dict] = None
    affected_entities: Optional[dict] = None
    is_historic: bool = False


class AdvanceRequest(BaseModel):
    unit: str = "month"  # month/quarter/halfyear/year


class TickOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    tick_index: int
    unit: str
    from_date: datetime
    to_date: datetime
    summary: Optional[str] = None
