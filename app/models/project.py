"""作品系统模型：作品（电影等）与剧组关系。"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Numeric, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import ProjectType, ProjectStatus


class Project(Base):
    __tablename__ = "projects"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    type = Column(Enum(ProjectType, name="project_type"), nullable=False, default=ProjectType.FILM)
    title = Column(String(300), nullable=False)
    status = Column(Enum(ProjectStatus, name="project_status"), nullable=False, default=ProjectStatus.CONCEPT)
    # Phase2 建立 companies 表后收口为正式 FK
    company_id = Column(BigInteger, ForeignKey("companies.id"))            # 制作公司
    distribution_company_id = Column(BigInteger, ForeignKey("companies.id"))  # 发行公司
    release_year = Column(Integer)
    release_month = Column(Integer)

    # 多维度质量分项（剧本/导演/表演…），保留原始分项可追溯
    quality_metrics = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    composite_quality = Column(Numeric)
    box_office = Column(Numeric)
    audience_score = Column(Numeric)
    media_score = Column(Numeric)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProjectCast(Base):
    """人物↔作品 出演/职务关系。"""
    __tablename__ = "project_cast"

    id = Column(BigInteger, primary_key=True)
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=False)
    character_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)
    role = Column(String(200))
    billing = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
