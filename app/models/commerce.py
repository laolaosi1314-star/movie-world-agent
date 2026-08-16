"""§17.1 商业时尚与塌房违约金：品牌代言与杂志封面模型。

设计原则（与全局蓝图一致）：
  - 确定性：代言费/违约金/封面的商业价值均为确定性函数（无 random），可重放、可解释；
  - 多世界隔离：所有查询按 world_id 过滤；
  - 与 §17.3 塌房强耦合：人物丑闻塌房（COLLAPSED）时，带道德条款的生效代言自动进入
    `breached`（触发违约金），商业价值 `commercial_value` 重挫，未刊登封面取消——
    「黑料/塌房（§17.3）」与「真金白银的商业帝国（§17.1）」在"商业—舆论—资本"闭环交汇；
  - 玩家（GM/运营角色）经 `Intervention` 审计留痕（commerce:manage 权限网关）。
"""
from sqlalchemy import (
    DateTime,
    Enum,
    BigInteger, Integer, String, Text, Numeric, Boolean, Column, ForeignKey, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.enums import EndorsementTier, ContractStatus, MagazineTier


class Endorsement(Base):
    """一条品牌代言合约：从签约生效到协商解约/塌房违约/到期。"""
    __tablename__ = "endorsements"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    character_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)

    brand_name = Column(String(200), nullable=False)
    category = Column(String(100))                 # 品类：美妆/腕表/服饰/饮品…
    tier = Column(Enum(EndorsementTier, name="endorsement_tier"), nullable=False,
                  default=EndorsementTier.MASS)
    # 代言费（单位：万元/年）；违约金比例 0-1（按剩余年限计赔）
    annual_fee = Column(Integer, nullable=False, default=0)
    penalty_rate = Column(Numeric, nullable=False, default=0.5)
    has_morals_clause = Column(Boolean, nullable=False, default=True)  # 道德条款：塌房即违约

    signed_tick = Column(BigInteger, nullable=False)
    duration_ticks = Column(Integer, nullable=False, default=12)       # 合约时长（tick）
    status = Column(Enum(ContractStatus, name="contract_status"), nullable=False,
                    default=ContractStatus.ACTIVE)

    terminated_tick = Column(BigInteger)        # 解约/违约发生的 tick
    penalty_amount = Column(Integer)            # 实赔违约金（万元），仅 breached 有值
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())


class MagazineCover(Base):
    """一次杂志封面拍摄/刊登（时尚资源，提升商业价值与曝光）。"""
    __tablename__ = "magazine_covers"

    id = Column(BigInteger, primary_key=True)
    world_id = Column(BigInteger, ForeignKey("world.id"), nullable=False)
    character_id = Column(BigInteger, ForeignKey("characters.id"), nullable=False)

    magazine_name = Column(String(200), nullable=False)
    tier = Column(Enum(MagazineTier, name="magazine_tier"), nullable=False,
                  default=MagazineTier.SECOND_TIER)
    issue_tick = Column(BigInteger, nullable=False)  # 计划/实际刊登的 tick
    theme = Column(String(200))                      # 封面主题
    fee = Column(Integer)                            # 封面费（万元，可空）
    prestige = Column(Integer, nullable=False, default=50)  # 时尚声望加成 0-100

    status = Column(Enum(ContractStatus, name="contract_status"), nullable=False,
                    default=ContractStatus.ACTIVE)   # ACTIVE=已排期/已刊登；TERMINATED=塌房取消
    cancelled_tick = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())
