"""世界（存档）相关 Schema。"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class WorldCreate(BaseModel):
    name: str
    description: Optional[str] = None
    seed_config: Optional[dict] = None


class WorldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    current_year: int
    current_month: int
    industry_status: str
    total_ticks: int
    status: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
