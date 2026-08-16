"""作品相关 Schema。"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    type: str = "film"
    title: str
    status: Optional[str] = "concept"
    quality_metrics: Optional[dict] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    type: str
    title: str
    status: str
    quality_metrics: dict = {}
    composite_quality: Optional[float] = None
    box_office: Optional[float] = None
    audience_score: Optional[float] = None
    media_score: Optional[float] = None
    created_at: Optional[datetime] = None


class ProjectFinancingIn(BaseModel):
    """投资人 / GM 为作品注资（项目融资），受 project:invest 权限网关约束。"""
    amount: float                       # 融资金额（亿元，或项目自定义单位）
    investor_name: Optional[str] = None  # 出资方（公司/个人/玩家名）
    note: Optional[str] = None
