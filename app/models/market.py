"""市场系统模型：整体市场快照（环境背景）与单作品市场表现。"""
from sqlalchemy import (
    Enum,
    DateTime,
    BigInteger, Integer, String, Text, Numeric, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import MarketOutcome, WorkDomain


class MarketSnapshot(Base):
    """每个 tick 记录整体市场环境，作为票房模型的背景变量。"""
    __tablename__ = "market_snapshots"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    tick_id = Column(BigInteger, ForeignKey("simulation_ticks.id"))
    snapshot_date = Column(DateTime(timezone=True), nullable=False)
    environment = Column(String(50))          # 繁荣/平稳/低迷
    heat = Column(Numeric)                    # 市场热度
    total_box_office = Column(Numeric)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProjectMarket(Base):
    """单作品市场表现：票房因果模型结果与可解释因子。"""
    __tablename__ = "project_market"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=False)
    tick_id = Column(BigInteger, ForeignKey("simulation_ticks.id"))
    # 领域轴：该条表现所属领域（电影/电视/音乐）；语义泛化为"作品市场/口碑表现"（§15.3）
    domain = Column(Enum(WorkDomain, name="work_domain"))
    release_slot = Column(String(50))         # 档期
    box_office = Column(Numeric)              # 亿元（film）
    audience_score = Column(Numeric)          # 三领域通用口碑分
    media_score = Column(Numeric)             # 三领域通用媒体分
    # ===== 电视 / 音乐 领域指标（film 行留 NULL）=====
    rating = Column(Numeric)                  # 收视率 %（tv）
    sales = Column(Numeric)                   # 销量 万（music）
    streams = Column(Numeric)                 # 流媒体播放 万次（music）
    chart_position = Column(Integer)          # 榜单最高名次（music）
    # 计算所用因果因子（可解释），如 {actor_value:78, director_value:65, ...}
    factors = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    # 口碑轨迹：高开低走/口碑逆袭…
    word_of_mouth_trajectory = Column(String(50))
    outcome = Column(Enum(MarketOutcome, name="market_outcome"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
