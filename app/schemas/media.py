"""媒体系统 Schema。"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MediaOutletCreate(BaseModel):
    name: str
    outlet_type: str = "serious"          # 对应 MediaOutletType
    stance: str = "neutral"               # 对应 MediaStance
    credibility: int = 50                 # 0-100
    preferred_categories: List[str] = []
    preferred_genres: List[str] = []
    founded_year: Optional[int] = None


class MediaOutletUpdate(BaseModel):
    """上帝模式可微调媒体机构属性（经 interventions 审计）。"""
    name: Optional[str] = None
    stance: Optional[str] = None
    credibility: Optional[int] = None
    preferred_categories: Optional[List[str]] = None


class MediaOutletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    name: str
    outlet_type: str
    stance: str
    credibility: int
    preferred_categories: List[str] = []
    preferred_genres: List[str] = []
    founded_year: Optional[int] = None
    status: str = "active"
    created_at: Optional[datetime] = None
