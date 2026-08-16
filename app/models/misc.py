"""杂项模型：上帝模式干预审计、Agent 记忆。"""
from sqlalchemy import (
    Enum,
    BigInteger, String, Text, DateTime, Boolean, Float, Integer,
    Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import InterventionType, MemoryScope


class Intervention(Base):
    """一切人工干预（上帝模式）的审计留痕，世界历史不被静默改写。"""
    __tablename__ = "interventions"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(String(100))  # 操作者，本期默认 'god'
    tick_id = Column(BigInteger, ForeignKey("simulation_ticks.id"))
    world_id = Column(BigInteger, ForeignKey("world.id"))
    target_type = Column(String(50), nullable=False)  # character/project/award...
    target_id = Column(BigInteger, nullable=False)
    intervention_type = Column(Enum(InterventionType, name="intervention_type"), nullable=False)
    field = Column(String(100))
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Memory(Base):
    """Agent 记忆：短期/长期/世界三层（Phase 5 完整落地）。

    三层语义：
      - short：单 tick 内的工作记忆（草稿），按 ttl/expires_tick 物理过期清理；
      - long ：跨 tick 持久化记忆，经"巩固"从短期提升而来，受遗忘曲线衰减；
      - world：全 Agent 共享的世界集体知识，永不衰减、永不休眠。

    检索权重 = importance × 近因因子(确定性指数衰减) × 频率因子(access_count)；
    长期记忆权重跌破阈值为休眠（保留不删，强线索仍可唤回）。
    """
    __tablename__ = "memories"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    agent = Column(String(100), nullable=False)
    scope = Column(Enum(MemoryScope, name="memory_scope"), nullable=False)
    key = Column(String(200), nullable=False)
    value = Column(JSONB, nullable=False)
    importance = Column(Float, nullable=False, server_default="0.5")
    access_count = Column(Integer, nullable=False, server_default="0")
    last_accessed_tick = Column(BigInteger)
    expires_at = Column(DateTime(timezone=True))
    expires_tick = Column(BigInteger)
    is_dormant = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
