"""§17.1 商业时尚与塌房违约金：请求/响应 Schema。"""
from typing import Optional
from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import EndorsementTier, ContractStatus, MagazineTier


# ===== 代言 =====
class EndorsementCreate(BaseModel):
    character_id: int
    brand_name: Optional[str] = Field(None, description="品牌名；留空则按 tier 从目录择一")
    category: Optional[str] = None
    tier: EndorsementTier = EndorsementTier.MASS
    annual_fee: int = Field(0, description="代言费（万元/年）")
    penalty_rate: float = Field(0.5, ge=0, le=1)
    has_morals_clause: bool = True
    duration_ticks: int = Field(12, gt=0)
    signed_tick: Optional[int] = Field(None, description="签约 tick；默认当前 world.total_ticks")


class EndorsementTerminate(BaseModel):
    voluntary: bool = Field(True, description="True=协商解约(terminated,无违约金)；False=标记违约")
    note: Optional[str] = None


class EndorsementOut(BaseModel):
    id: int
    world_id: int
    character_id: int
    brand_name: str
    category: Optional[str]
    tier: str
    annual_fee: int
    penalty_rate: float
    has_morals_clause: bool
    signed_tick: int
    duration_ticks: int
    status: str
    terminated_tick: Optional[int]
    penalty_amount: Optional[int]

    class Config:
        from_attributes = True


# ===== 杂志封面 =====
class MagazineCoverCreate(BaseModel):
    character_id: int
    magazine_name: Optional[str] = Field(None, description="刊物名；留空则按 tier 从目录择一")
    tier: MagazineTier = MagazineTier.SECOND_TIER
    issue_tick: Optional[int] = Field(None, description="刊登 tick；默认下一 tick")
    theme: Optional[str] = None
    fee: Optional[int] = None
    prestige: int = 50


class MagazineCoverOut(BaseModel):
    id: int
    world_id: int
    character_id: int
    magazine_name: str
    tier: str
    issue_tick: int
    theme: Optional[str]
    fee: Optional[int]
    prestige: int
    status: str
    cancelled_tick: Optional[int]

    class Config:
        from_attributes = True


# ===== 商业概览（人物视角） =====
class CommercialSummary(BaseModel):
    character_id: int
    commercial_value: Optional[float]
    active_endorsements: int
    breached_endorsements: int
    active_covers: int
    cancelled_covers: int
    total_penalty_paid: int
