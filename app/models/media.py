"""媒体系统模型：媒体机构（媒体也是一种随世界演化的实体）。"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import MediaOutletType, MediaStance


class MediaOutlet(Base):
    """媒体机构：拥有立场、公信力、偏好类型与风格标签。

    不同媒体对同一事件的报道角度不同（严肃媒体重事实、八卦媒体重情绪、
    行业媒体重数据），这是媒体系统产生"舆论多样性"的来源。
    """
    __tablename__ = "media_outlets"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    name = Column(String(200), nullable=False)
    outlet_type = Column(Enum(MediaOutletType, name="media_outlet_type"), nullable=False, default=MediaOutletType.SERIOUS)
    stance = Column(Enum(MediaStance, name="media_stance"), nullable=False, default=MediaStance.NEUTRAL)
    credibility = Column(Integer, nullable=False, default=50)   # 公信力 0-100
    # 偏好报道的事件类别（JSON 数组），如 ["boxoffice","award_prediction"]
    preferred_categories = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    # 偏好题材（JSON 数组），如 ["sci_fi","romance"]
    preferred_genres = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)
    founded_year = Column(Integer)
    status = Column(String(20), nullable=False, default="active")  # active/archived
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
