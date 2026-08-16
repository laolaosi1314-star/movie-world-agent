"""§17.3 舆论与危机公关相关 Schema。"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.enums import ScandalType, ScandalStage, PRStrategy


class ScandalCreate(BaseModel):
    """黑料爆料（GM/运营，crisis:manage 权限）。"""
    character_id: int
    scandal_type: str = "other"          # ScandalType 取值
    title: str
    severity: int = 5                    # 1-10
    evidence_strength: int = 5           # 1-10
    is_confirmed: bool = False
    related_project_id: Optional[int] = None
    exposed: bool = True                 # True=立即曝光(SPREADING)；False=先潜伏(LATENT)
    notes: Optional[str] = None


class ScandalExpose(BaseModel):
    """曝光一条潜伏丑闻（可选备注）。"""
    notes: Optional[str] = None


class PRStrategyIn(BaseModel):
    """发起一次公关动作（多阶段公关）。"""
    strategy: str                        # PRStrategy 取值
    note: Optional[str] = None


class ScandalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    character_id: int
    related_project_id: Optional[int] = None
    scandal_type: str
    title: str
    severity: int
    evidence_strength: int
    is_confirmed: bool
    stage: str
    heat: int
    public_opinion: int
    exposed_tick: Optional[int] = None
    erupted_tick: Optional[int] = None
    resolved_tick: Optional[int] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class CrisisPROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    scandal_id: int
    strategy: str
    by_player_id: Optional[str] = None
    impact: dict = {}
    note: Optional[str] = None
    created_at: Optional[datetime] = None
