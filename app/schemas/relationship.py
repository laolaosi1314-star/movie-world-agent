"""§17.2 人际情感网络 与 人生档案馆 相关 Schema。"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import RomanceType, RomanceStatus


# ===== 情感关系 =====
class RomanceCreate(BaseModel):
    character_a_id: int
    character_b_id: int
    romance_type: str = "dating"        # RomanceType 取值
    is_public: bool = False             # True=官宣公开；False=地下（随 tick 自然泄露）
    publicness: int = Field(0, ge=0, le=100)
    child_count: int = 0
    notes: Optional[str] = None


class RomanceReveal(BaseModel):
    """主动官宣公开（可备注）。"""
    notes: Optional[str] = None


class RomanceEnd(BaseModel):
    reason: Optional[str] = Field(None, description="结束原因：分手/离婚/因丑闻拆散")


class RomanceAddChild(BaseModel):
    """增加子女数量（结婚/稳定关系后）。"""
    count: int = Field(1, ge=1, le=5)
    notes: Optional[str] = None


class RomanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    character_a_id: int
    character_b_id: int
    romance_type: str
    status: str
    is_public: bool
    publicness: int
    reacted_tick: Optional[int] = None
    child_count: int
    started_tick: int
    ended_tick: Optional[int] = None
    ended_reason: Optional[str] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


# ===== 人生档案馆（只读聚合） =====
class TimelineEntry(BaseModel):
    year: Optional[int] = None
    kind: str
    title: str
    detail: str = ""
    significance: int = 1


class LifeArchiveOut(BaseModel):
    character_id: int
    name: str
    type: str
    birth_year: Optional[int] = None
    career_stage: str
    status: str
    heat: int
    commercial_value: Optional[float] = None
    award_summary: Dict[str, Any] = {}
    awards: List[Dict[str, Any]] = []
    commercial: List[Dict[str, Any]] = []
    scandals: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []
    career_history: List[Dict[str, Any]] = []
    major_events: List[Dict[str, Any]] = []
    timeline: List[TimelineEntry] = []
    legacy_footnotes: List[Dict[str, Any]] = []
