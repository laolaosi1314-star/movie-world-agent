"""公司系统模型：公司（拥有自身生命周期）与公司发展历程。"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Numeric, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import (
    CompanyType, CompanyStatus, CompanyStyle,
)


class Company(Base):
    __tablename__ = "companies"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(Enum(CompanyType, name="company_type"), nullable=False, default=CompanyType.PRODUCTION)
    founded_year = Column(Integer)
    country = Column(String(100))
    status = Column(Enum(CompanyStatus, name="company_status"), nullable=False, default=CompanyStatus.ACTIVE)
    # 风格由产出推导（非写死），见 CompanyAgent._derive_style
    style_tag = Column(Enum(CompanyStyle, name="company_style"))

    # 核心资产与能力
    capital = Column(Numeric, nullable=False, default=0)
    cash = Column(Numeric, nullable=False, default=0)
    market_share = Column(Numeric)
    talent_resources = Column(Integer, default=0)
    production_capability = Column(Numeric)
    distribution_capability = Column(Numeric)
    art_reputation = Column(Numeric)
    commercial_reputation = Column(Numeric)
    industry_position = Column(String(50))

    attributes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    history = relationship("CompanyHistory", back_populates="company")


class CompanyHistory(Base):
    """公司发展历程，追加写入、对应生命周期里程碑（永不覆盖）。"""
    __tablename__ = "company_history"

    id = Column(BigInteger, primary_key=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer)
    title = Column(Text, nullable=False)
    description = Column(Text)
    event_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="history")
