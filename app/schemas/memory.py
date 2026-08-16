"""记忆系统 Schema（Phase 5）。"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    agent: str
    scope: str
    key: str
    value: Dict[str, Any]
    importance: float = 0.5
    access_count: int = 0
    last_accessed_tick: Optional[int] = None
    expires_tick: Optional[int] = None
    is_dormant: bool = False
    created_at: Optional[datetime] = None


class MemoryWrite(BaseModel):
    """上帝模式 / 外部写入一条记忆。"""
    agent: str
    scope: str  # short/long/world
    key: str
    value: Dict[str, Any]
    importance: float = 0.5
    ttl_ticks: Optional[int] = None  # 仅 short 生效
    expires_at: Optional[datetime] = None


class MemoryQuery(BaseModel):
    scope: Optional[str] = None
    agent: Optional[str] = None
    key_prefix: Optional[str] = None
    top_k: int = 20
    include_dormant: bool = False


class MemoryConsolidateResult(BaseModel):
    consolidated: int
    purged: int
