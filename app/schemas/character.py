"""人物相关 Schema。"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CharacterCreate(BaseModel):
    type: str  # actor/director/...
    name: str
    birth_year: Optional[int] = None
    nationality: Optional[str] = None
    career_stage: Optional[str] = "debut"
    attributes: Optional[dict] = None


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    type: str
    name: str
    birth_year: Optional[int] = None
    nationality: Optional[str] = None
    status: str
    career_stage: str
    is_in_hall_of_fame: bool = False
    attributes: dict = {}
    created_at: Optional[datetime] = None
