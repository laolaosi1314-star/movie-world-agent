"""玩家身份相关 Schema（Phase 6）。"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PlayerCreate(BaseModel):
    name: str
    role: str = "audience"   # PlayerRole 取值：audience / critic / investor / gm
    # 仅 CRITIC 使用：专长领域（WorkDomain 值列表，如 ["film","tv"]）；其余角色忽略。
    critic_domains: Optional[list[str]] = None
    bio: Optional[str] = None


class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    world_id: int
    name: str
    role: str
    critic_domains: Optional[list] = None
    bio: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class PlayerTokenOut(BaseModel):
    """创建玩家时一次性下发 player_key（Bearer 令牌）；之后不再明文出现。"""
    player: PlayerOut
    player_key: str


class PlayerCapability(BaseModel):
    """客户端可渲染的一个动作（供 App/H5 渲染按钮 / 能力探测）。"""
    key: str
    label: str
    permission: str
    requires_world_writable: bool


class PlayerMeOut(PlayerOut):
    """当前玩家身份 + 其角色在客户端可见/可发起的全部动作（能力集）。"""
    capabilities: list[str] = []
    actions: list[PlayerCapability] = []


class PlayerPortalOut(BaseModel):
    """面向 App/H5 首页的玩家视角聚合接口：身份 + 能力 + 世界快照 + 近期时间线。"""
    player: PlayerMeOut
    world: dict
    recent_events: list
