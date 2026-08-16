"""玩家身份（用户角色体系 Phase 6）。

无状态契约下的身份建模要点（与 API_CONTRACT §1 一致）：
  - 服务端**不保存会话**；玩家身份由每个请求的 `Authorization: Bearer <player_key>` 解析。
  - `player_key` 是创建玩家时一次性下发的秘密（64 位十六进制），客户端（App/H5）负责持有；
    服务端每次请求据此解析 Player 并校验其 world 作用域与角色边界。
  - 同一玩家可操作多个世界，但每次请求必须携带目标 `world_id`（路径参数），
    且 `player.world_id` 必须与请求路径的 `world_id` 一致，跨世界操作被拒绝。
"""
from sqlalchemy import (
    Enum,
    BigInteger, String, Text, DateTime, Boolean, Column, ForeignKey, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import PlayerRole


class Player(Base):
    __tablename__ = "players"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    role = Column(
        Enum(PlayerRole, name="player_role"),
        nullable=False,
        default=PlayerRole.AUDIENCE,
    )
    # 无状态鉴权载体：Bearer token 的秘密；一次性下发，唯一且不可反推玩家身份之外的世界状态。
    player_key = Column(String(64), nullable=False, unique=True, index=True)
    # 影评人专长领域（WorkDomain 值列表，如 ["film","tv"]）；仅 CRITIC 使用，其余角色为 NULL。
    critic_domains = Column(JSONB, nullable=True)
    bio = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    world = relationship("World", foreign_keys=[world_id])
