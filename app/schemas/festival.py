"""电影节相关 Schema。"""
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class FestivalCreate(BaseModel):
    name: str
    founded_year: Optional[int] = None
    location: Optional[str] = None
    level: Optional[str] = None       # international_a/international_b/...
    positioning: Optional[str] = None
    selection_rules: Optional[dict] = None
    jury: Optional[list] = None
    units: Optional[list] = None


class FestivalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    name: str
    founded_year: Optional[int] = None
    location: Optional[str] = None
    level: Optional[str] = None
    positioning: Optional[str] = None
    created_at: Optional[datetime] = None


class FestivalEditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    festival_id: int
    edition_number: int
    year: int
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class FestivalAwardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    edition_id: int
    category: str
    winner_project_id: Optional[int] = None
    winner_character_id: Optional[int] = None
    is_user_override: bool = False


class FestivalAwardSet(BaseModel):
    """上帝模式手动设定某届某单元奖项（可审计）。"""
    category: str
    winner_project_id: Optional[int] = None
    winner_character_id: Optional[int] = None
    reason: Optional[str] = None
