"""世界（存档）与模拟 tick 模型。"""
from sqlalchemy import (
    Enum,
    BigInteger, Integer, String, Text, DateTime, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import WorldStatus


class World(Base):
    __tablename__ = "world"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(200), nullable=False, default="影视世界")
    current_year = Column(Integer, nullable=False, default=2032)
    current_month = Column(Integer, nullable=False, default=6)
    industry_status = Column(String(50), nullable=False, default="繁荣")
    rng_seed = Column(BigInteger, nullable=False, default=0)
    total_ticks = Column(Integer, nullable=False, default=0)

    # 多世界管理扩展字段
    status = Column(Enum(WorldStatus, name="world_status"), nullable=False, default=WorldStatus.ACTIVE)
    description = Column(Text)
    seed_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    ticks = relationship("SimulationTick", back_populates="world")


class SimulationTick(Base):
    __tablename__ = "simulation_ticks"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    tick_index = Column(Integer, nullable=False)
    unit = Column(String(20), nullable=False)  # month/quarter/halfyear/year
    from_date = Column(DateTime(timezone=True), nullable=False)
    to_date = Column(DateTime(timezone=True), nullable=False)
    rng_seed_used = Column(BigInteger, nullable=False)
    summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    world = relationship("World", back_populates="ticks")
