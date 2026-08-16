"""新闻系统 Schema。"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NewsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    outlet_id: int
    tick_id: Optional[int] = None
    primary_event_id: Optional[int] = None
    related_event_ids: List[int] = []
    news_type: str
    headline: str
    body: Optional[str] = None
    fact_pack: Dict[str, Any] = {}
    render_engine: str
    outlet_snapshot: Dict[str, Any] = {}
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class NewsListOut(BaseModel):
    total: int
    items: List[NewsOut]
