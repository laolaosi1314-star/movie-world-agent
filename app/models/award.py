"""奖项体系模型：奖项档案、奖季、类别、提名、获奖、叙事统计、成就累计。

注意：设计文档原称这些表"已在 Phase 1 建表埋点"，但 0001_initial 迁移实际未创建，
故在 0002 迁移中正式建表并启用逻辑（见 BLUEPRINT.md【返工点】）。
"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Boolean, Date, Column, ForeignKey, func, text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import AwardNarrativeTag, AwardType, WorkDomain, CategoryKind


class Award(Base):
    """奖项档案：金屏奖（正奖）/ 金酸梅奖（负奖）等。"""
    __tablename__ = "awards"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    name = Column(String(200), nullable=False)
    founded_year = Column(Integer)
    organizer = Column(String(200))
    positioning = Column(Text)
    level = Column(String(50))
    award_type = Column(Enum(AwardType, name="award_type"), nullable=False,
                        default=AwardType.POSITIVE)
    # 领域轴：该奖项主领域（电影/电视/音乐）；单一奖项可混合不同领域类别（§15.2）
    domain = Column(Enum(WorkDomain, name="work_domain"), nullable=False,
                    default=WorkDomain.FILM)
    rules = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    seasons = relationship("AwardSeason", back_populates="award")
    categories = relationship("AwardCategory", back_populates="award")


class AwardSeason(Base):
    """奖季：每年一届，进入奖项季后跑资格→候选→提名→颁奖。"""
    __tablename__ = "award_seasons"

    id = Column(BigInteger, primary_key=True)
    award_id = Column(BigInteger, ForeignKey("awards.id"), nullable=False)
    season_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="upcoming")  # upcoming/ongoing/ceremony/done
    ceremony_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    award = relationship("Award", back_populates="seasons")


class AwardCategory(Base):
    """奖项类别定义：最佳影片/最差影片/最佳导演/最差表演…（含正负面）。"""
    __tablename__ = "award_categories"

    id = Column(BigInteger, primary_key=True)
    award_id = Column(BigInteger, ForeignKey("awards.id"), nullable=False)
    name = Column(String(100), nullable=False)
    award_type = Column(Enum(AwardType, name="award_type"), nullable=False,
                        default=AwardType.POSITIVE)
    # 领域轴：该类别所属领域（权威源）；kind 为该类别评判的客体种类（§15.3）
    domain = Column(Enum(WorkDomain, name="work_domain"), nullable=False,
                    default=WorkDomain.FILM)
    kind = Column(Enum(CategoryKind, name="category_kind"), nullable=False,
                  default=CategoryKind.PROJECT)
    rules = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    award = relationship("Award", back_populates="categories")


class Nomination(Base):
    """提名名单：某奖季某类别的候选（人物/作品/组合）。"""
    __tablename__ = "nominations"

    id = Column(BigInteger, primary_key=True)
    season_id = Column(BigInteger, ForeignKey("award_seasons.id"), nullable=False)
    category_id = Column(BigInteger, ForeignKey("award_categories.id"), nullable=False)
    category_name = Column(String(100), nullable=False)
    project_id = Column(BigInteger, ForeignKey("projects.id"))
    character_id = Column(BigInteger, ForeignKey("characters.id"))
    is_user_override = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Winner(Base):
    """最终获奖：与提名一一对应，is_user_override 标记上帝模式手动设定。"""
    __tablename__ = "winners"

    id = Column(BigInteger, primary_key=True)
    season_id = Column(BigInteger, ForeignKey("award_seasons.id"), nullable=False)
    category_id = Column(BigInteger, ForeignKey("award_categories.id"), nullable=False)
    category_name = Column(String(100), nullable=False)
    project_id = Column(BigInteger, ForeignKey("projects.id"))
    character_id = Column(BigInteger, ForeignKey("characters.id"))
    is_user_override = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AwardSeasonStat(Base):
    """每届的"故事点"：最大赢家/遗珠/冷门/最年轻/连庄/横扫…。"""
    __tablename__ = "award_season_stats"

    id = Column(BigInteger, primary_key=True)
    season_id = Column(BigInteger, ForeignKey("award_seasons.id"), nullable=False)
    tag = Column(Enum(AwardNarrativeTag, name="award_narrative_tag"), nullable=False)
    target_type = Column(String(50))
    target_id = Column(BigInteger)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AwardAchievement(Base):
    """人物×奖项 成就累计（自动生成"五提一中"等）。"""
    __tablename__ = "award_achievements"

    id = Column(BigInteger, primary_key=True)
    award_id = Column(BigInteger, ForeignKey("awards.id"), nullable=False)
    character_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)
    nominations_count = Column(Integer, nullable=False, default=0)
    wins_count = Column(Integer, nullable=False, default=0)
    note = Column(Text)  # "五提一中"
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # 保证同一奖项下同一人物只有一行
        UniqueConstraint("award_id", "character_id", name="uq_achv_award_char"),
    )
