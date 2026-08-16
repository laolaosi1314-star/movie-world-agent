"""电影节系统模型：电影节档案、逐年届次、单元选拔与奖项。"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Date, Boolean, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import (
    FestivalLevel, FestivalSection, EditionStatus,
)


class Festival(Base):
    __tablename__ = "festivals"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    name = Column(String(200), nullable=False)
    founded_year = Column(Integer)
    location = Column(String(100))
    level = Column(Enum(FestivalLevel, name="festival_level"))
    positioning = Column(Text)
    selection_rules = Column(JSONB)   # 选拔规则
    jury = Column(JSONB)              # 评委
    units = Column(JSONB)             # 单元定义
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    editions = relationship("FestivalEdition", back_populates="festival")


class FestivalEdition(Base):
    """逐年届次：upcoming → ongoing → completed。"""
    __tablename__ = "festival_editions"

    id = Column(BigInteger, primary_key=True)
    festival_id = Column(BigInteger, ForeignKey("festivals.id"), nullable=False)
    edition_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    status = Column(Enum(EditionStatus, name="edition_status"), nullable=False, default=EditionStatus.UPCOMING)
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    festival = relationship("Festival", back_populates="editions")
    selections = relationship("FestivalSelection", back_populates="edition")
    awards = relationship("FestivalAward", back_populates="edition")


class FestivalSelection(Base):
    """单元入围 / 展映。"""
    __tablename__ = "festival_selections"

    id = Column(BigInteger, primary_key=True)
    edition_id = Column(BigInteger, ForeignKey("festival_editions.id"), nullable=False)
    section = Column(Enum(FestivalSection, name="festival_section"), nullable=False)
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=False)
    selection_type = Column(String(20), nullable=False, default="selected")  # selected/showcase
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    edition = relationship("FestivalEdition", back_populates="selections")


class FestivalAward(Base):
    """单届电影节的颁奖结果（单元奖项）。"""
    __tablename__ = "festival_awards"

    id = Column(BigInteger, primary_key=True)
    edition_id = Column(BigInteger, ForeignKey("festival_editions.id"), nullable=False)
    category = Column(String(100), nullable=False)  # 最佳导演/最佳男演员…
    winner_project_id = Column(BigInteger, ForeignKey("projects.id"))
    winner_character_id = Column(BigInteger, ForeignKey("characters.id"))
    is_user_override = Column(Boolean, nullable=False, default=False)  # 上帝模式手动设定
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    edition = relationship("FestivalEdition", back_populates="awards")
