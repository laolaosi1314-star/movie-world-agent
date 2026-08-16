"""§17.3 舆论与危机公关：黑料/丑闻与多阶段公关模型。

设计原则（与全局蓝图一致）：
  - 确定性：丑闻演化与公关舆论恢复曲线均为 tick 索引的确定性函数（无 random），
    可重放、可解释；
  - 多世界隔离：所有查询按 world_id 过滤；
  - 无缝复用 §14：Scandal 严重度/证据强度在演化中写入世界记忆 `sharp_topics`，
    由媒体 Agent 自动生成争议通稿；爆发/关键节点另产「争议」事件进入同一闭环；
  - 玩家（GM/运营角色）经 `Intervention` 审计留痕（crisis:manage 权限网关）。
"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Boolean, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import ScandalType, ScandalStage, PRStrategy


class Scandal(Base):
    """一条黑料/丑闻：从潜伏到爆发、处理、平息或塌房的全生命周期。"""
    __tablename__ = "scandals"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    character_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)
    # 涉案作品（如有，如"某剧轧戏""某专辑抄袭"），用于表达层与未来联动
    related_project_id = Column(BigInteger, ForeignKey("projects.id"))

    scandal_type = Column(Enum(ScandalType, name="scandal_type"), nullable=False,
                          default=ScandalType.OTHER)
    title = Column(Text, nullable=False)
    # 严重度 1-10、证据强度 1-10、是否实锤
    severity = Column(Integer, nullable=False, default=5)
    evidence_strength = Column(Integer, nullable=False, default=5)
    is_confirmed = Column(Boolean, nullable=False, default=False)

    stage = Column(Enum(ScandalStage, name="scandal_stage"), nullable=False,
                   default=ScandalStage.LATENT)
    # 舆情热度 0-100（驱动媒体关注度）；舆情分 0-100（复用 media_score 口径方向，50=中性）
    heat = Column(Integer, nullable=False, default=0)
    public_opinion = Column(Integer, nullable=False, default=50)

    # 关键 tick 锚点（确定性演化用，可重放）
    exposed_tick = Column(BigInteger)     # 进入 SPREADING 的 tick
    erupted_tick = Column(BigInteger)     # 进入 ERUPTED 的 tick
    resolved_tick = Column(BigInteger)    # 进入 RESOLVED/COLLAPSED 的 tick

    # 操作者：玩家 id（GM/运营）经 Intervention 审计；系统演化记为 'system'/'world'
    created_by = Column(String(100), default="system")
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())


class CrisisPR(Base):
    """一次公关动作（冷处理/律师函/道歉/买热搜/洗白反转）的留痕与确定性结算结果。"""
    __tablename__ = "crisis_pr"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    scandal_id = Column(BigInteger, ForeignKey("scandals.id"), nullable=False)

    strategy = Column(Enum(PRStrategy, name="pr_strategy"), nullable=False)
    by_player_id = Column(String(100))     # 发起公关的玩家 id（GM/运营）
    # 本次公关的确定性结算（纯函数 evaluate_pr 的输出，便于审计与可解释）
    impact = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
