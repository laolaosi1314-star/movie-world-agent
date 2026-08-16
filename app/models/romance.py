"""§17.2 人际情感网络：恋情 / 绯闻 / 结婚生子 与粉丝蝴蝶效应模型。

设计原则（与全局蓝图一致）：
  - 确定性：曝光演化、粉丝应援/脱粉回踩的舆论曲线均为 tick 索引的确定性函数（无 random），
    可重放、可解释；
  - 多世界隔离：所有查询按 world_id 过滤；
  - 与 §17.3 强耦合：一方卷入「出轨(affair)」丑闻（SPREADING/ERUPTED/COLLAPSED）时，
    本关系自动结束（分手/离婚），并触发该方的脱粉回踩——「黑料(§17.3) → 情感崩塌(§17.2)」；
  - 无缝复用 §14 闭环：公开恋情 / 回踩等写「情感争议」事件（媒体当 tick 生成 CONTROVERSY 新闻）
    + 世界记忆 sharp_topics(domain=relationship)，媒体 Agent 下一 tick 自动生成争议通稿（零改动）；
  - 玩家（GM/运营角色）经 `Intervention` 审计留痕（relationship:manage 权限网关）。
"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Boolean, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import RomanceType, RomanceStatus


class Romance(Base):
    """两个人物之间的一条情感关系：从地下/疑似到公开、结婚、生子，乃至分手/离婚。"""
    __tablename__ = "romances"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    character_a_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)
    character_b_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)

    romance_type = Column(Enum(RomanceType, name="romance_type"), nullable=False,
                          default=RomanceType.DATING)
    status = Column(Enum(RomanceStatus, name="romance_status"), nullable=False,
                    default=RomanceStatus.ACTIVE)
    # 是否公开：地下(SECRET)->公开 由 publicness 累积触发，或由玩家 reveal 主动公开
    is_public = Column(Boolean, nullable=False, default=False)
    # 曝光度 0-100：地下关系随时间自然泄露（确定性），达阈值自动公开
    publicness = Column(Integer, nullable=False, default=0)
    # 已公开时是否已结算过粉丝蝴蝶效应（保证仅触发一次）
    reacted_tick = Column(BigInteger)
    # 子女数量（结婚/稳定关系后可由玩家 add_child 增加）
    child_count = Column(Integer, nullable=False, default=0)

    started_tick = Column(BigInteger, nullable=False)
    ended_tick = Column(BigInteger)
    ended_reason = Column(Text)            # 分手 / 因丑闻拆散 / 离婚 等
    created_by = Column(String(100), default="system")
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())
