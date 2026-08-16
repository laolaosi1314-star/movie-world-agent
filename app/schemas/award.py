"""奖项体系相关 Schema。"""
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class AwardCreate(BaseModel):
    name: str
    founded_year: Optional[int] = None
    organizer: Optional[str] = None
    positioning: Optional[str] = None
    level: Optional[str] = None
    award_type: str = "positive"   # positive / negative
    domain: str = "film"           # film / tv / music（领域轴，§15.2）
    rules: Optional[dict] = None


class AwardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    name: str
    founded_year: Optional[int] = None
    organizer: Optional[str] = None
    positioning: Optional[str] = None
    level: Optional[str] = None
    award_type: str = "positive"
    domain: str = "film"


class AwardCategoryCreate(BaseModel):
    name: str
    award_type: str = "positive"   # positive / negative
    domain: str = "film"           # film / tv / music
    kind: str = "project"          # 类目客体种类（§15.3 CategoryKind）
    rules: Optional[dict] = None


class AwardCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    award_id: int
    name: str
    award_type: str = "positive"
    domain: str = "film"
    kind: str = "project"
    rules: Optional[dict] = None


class WinnerSet(BaseModel):
    """上帝模式设定某奖季某类别获奖（可审计）。"""
    category_id: int
    project_id: Optional[int] = None
    character_id: Optional[int] = None
    reason: Optional[str] = None


class WinnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    category_id: int
    category_name: str
    project_id: Optional[int] = None
    character_id: Optional[int] = None
    is_user_override: bool = False


class NominationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    category_id: int
    category_name: str
    project_id: Optional[int] = None
    character_id: Optional[int] = None
    is_user_override: bool = False


class AwardSeasonStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    tag: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    description: Optional[str] = None


class AwardAchievementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    award_id: int
    character_id: int
    nominations_count: int
    wins_count: int
    note: Optional[str] = None
