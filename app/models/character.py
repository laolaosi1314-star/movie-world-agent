"""人物系统模型：人物、属性变更日志、生涯时间线、关系边。"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Date, Numeric, Boolean, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import (
    CharacterType, CharacterStatus, CareerStage,
)


class Character(Base):
    __tablename__ = "characters"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    type = Column(Enum(CharacterType, name="character_type"), nullable=False)
    name = Column(String(200), nullable=False)
    birth_year = Column(Integer)
    nationality = Column(String(100))
    # Phase2 建立 companies 表后收口为正式 FK
    company_id = Column(BigInteger, ForeignKey("companies.id"))
    # agent_id 指向经纪人（同表人物），暂不强制 FK 以避免循环依赖
    agent_id = Column(BigInteger)
    status = Column(Enum(CharacterStatus, name="character_status"), nullable=False, default=CharacterStatus.ACTIVE)
    career_stage = Column(Enum(CareerStage, name="career_stage"), nullable=False, default=CareerStage.DEBUT)
    is_in_hall_of_fame = Column(Boolean, nullable=False, default=False)
    archived_at = Column(Date)
    # §17.1 商业价值（万级指数，与 quality_metrics/audience_score 正交）；null=尚未初始化
    commercial_value = Column(Numeric, nullable=True)

    attributes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CharacterAttributeLog(Base):
    """属性每次变更留痕，保证可追溯（防失真）。"""
    __tablename__ = "character_attribute_log"

    id = Column(BigInteger, primary_key=True)
    character_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)
    tick_id = Column(BigInteger, ForeignKey("simulation_ticks.id"))
    field = Column(String(100), nullable=False)
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    reason = Column(Text)
    event_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CharacterCareerHistory(Base):
    """人物生涯时间线，追加写入、永不覆盖。"""
    __tablename__ = "character_career_history"

    id = Column(BigInteger, primary_key=True)
    character_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer)
    title = Column(Text, nullable=False)
    description = Column(Text)
    event_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Relationship(Base):
    """通用关系边：人物-人物 / 人物-公司 / 作品-奖项 等。"""
    __tablename__ = "relationships"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"))
    from_type = Column(String(50), nullable=False)
    from_id = Column(BigInteger, nullable=False)
    to_type = Column(String(50), nullable=False)
    to_id = Column(BigInteger, nullable=False)
    relation = Column(String(100), nullable=False)
    weight = Column(Numeric)
    started_year = Column(Integer)
    ended_year = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
