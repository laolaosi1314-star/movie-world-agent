"""市场 / 票房相关 Schema。"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MarketSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    snapshot_date: datetime
    environment: Optional[str] = None
    heat: Optional[float] = None
    total_box_office: Optional[float] = None
    notes: Optional[str] = None


class ProjectMarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    project_id: int
    release_slot: Optional[str] = None
    box_office: Optional[float] = None
    audience_score: Optional[float] = None
    media_score: Optional[float] = None
    factors: dict = {}
    word_of_mouth_trajectory: Optional[str] = None
    outcome: Optional[str] = None
