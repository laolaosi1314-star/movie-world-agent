"""事件日志模型。"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, String, Text, Date, Boolean, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import EventLevel


class Event(Base):
    __tablename__ = "events"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    tick_id = Column(BigInteger, ForeignKey("simulation_ticks.id"))
    event_date = Column(Date, nullable=False)
    level = Column(Enum(EventLevel, name="event_level"), nullable=False, default=EventLevel.NORMAL)
    category = Column(String(100))
    title = Column(Text, nullable=False)
    description = Column(Text)
    # 因果链：结构化原因列表，如 [{factor:"表演",value:94}, ...]
    causal_chain = Column(JSONB)
    affected_entities = Column(JSONB)
    is_historic = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
