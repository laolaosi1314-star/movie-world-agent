"""新闻系统模型：报道条目。

关键设计：news.fact_pack 原样存储结构化事实（JSONB），文本由渲染器基于
fact_pack 生成。这样以后接入 LLM 后，可以拿历史 fact_pack 重新生成全部报道，
无需重跑世界。
"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import NewsType, RenderEngine


class News(Base):
    """一条媒体报道（快讯/评论/专访/票房/奖项预测/红毯/争议/行业新闻）。"""
    __tablename__ = "news"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    outlet_id = Column(BigInteger, ForeignKey("media_outlets.id"), nullable=False)
    tick_id = Column(BigInteger, ForeignKey("simulation_ticks.id"))
    # 关联到的事件（可选，可一条新闻对应多条事件，见 below_events）
    primary_event_id = Column(BigInteger, ForeignKey("events.id"))
    related_event_ids = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)

    news_type = Column(Enum(NewsType, name="news_type"), nullable=False, default=NewsType.BULLETIN)
    headline = Column(Text, nullable=False)
    # 正文。render_engine 决定其来源（模板 or LLM）。
    body = Column(Text)
    # 原样保留的结构化事实包（谁/何时/做了什么/关键数值/因果因子）。
    fact_pack = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    render_engine = Column(Enum(RenderEngine, name="render_engine"), nullable=False, default=RenderEngine.TEMPLATE)
    # 渲染时使用的 outlet 风格快照（stance/credibility 等），保证重渲染可复现。
    outlet_snapshot = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    published_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
