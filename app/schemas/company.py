"""公司相关 Schema。"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CompanyCreate(BaseModel):
    name: str
    type: str = "production"          # production/distribution/agency/streaming/capital
    founded_year: Optional[int] = None
    country: Optional[str] = None
    style_tag: Optional[str] = None
    capital: Optional[float] = 0
    cash: Optional[float] = 0
    attributes: Optional[dict] = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    name: str
    type: str
    founded_year: Optional[int] = None
    country: Optional[str] = None
    status: str
    style_tag: Optional[str] = None
    capital: float = 0
    cash: float = 0
    market_share: Optional[float] = None
    talent_resources: Optional[int] = 0
    production_capability: Optional[float] = None
    distribution_capability: Optional[float] = None
    art_reputation: Optional[float] = None
    commercial_reputation: Optional[float] = None
    attributes: dict = {}
    created_at: Optional[datetime] = None


class CompanyHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    year: int
    month: Optional[int] = None
    title: str
    description: Optional[str] = None
