"""§17.1 商业时尚与塌房违约金 Agent：品牌代言 · 杂志封面 · 塌房违约金结算。

底层逻辑（确定性、可重放、无随机）：
  1. 商业价值：人物 `commercial_value`（正式列，并镜像进 attributes 供市场 Agent 读取）——
     由代言/封面贡献，塌房时重挫。
  2. 塌房违约金（与 §17.3 强耦合）：当人物丑闻塌房（COLLAPSED），`apply_collapse_penalty`
     自动遍历其带道德条款的生效代言 → 状态 `breached` 并按 `penalty_rate × 剩余年限` 计赔；
     商业价值按严重度重挫；未刊登封面取消。这就是"黑料/塌房（§17.3）→ 真金白银（§17.1）"的焊点。
  3. 无缝复用 §14 闭环：塌房违约金写「商业塌房」事件 + 世界记忆 `sharp_topics`(domain=commerce)，
     媒体 Agent 下一 tick 自动生成争议通稿（与 §17.3 同源，媒体 Agent 零改动）。
  4. 自动商务生成：每 tick 为高热度艺人确定性地接洽代言/封面（propensity 由 人气×tick 扰动 决定），
     绝不随机，可重放。
"""
from typing import Optional

from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.event import Event
from app.models.enums import (
    EventLevel, CharacterType, CharacterStatus, MemoryScope,
    EndorsementTier, ContractStatus, MagazineTier,
)
from app.models.character import Character
from app.models.commerce import Endorsement, MagazineCover
from app.models.crisis import Scandal, ScandalStage
from app.sim.memory import MemoryStore


# ===================== 确定性超参（可重放） =====================
CELEB_TYPES = {CharacterType.ACTOR, CharacterType.SINGER}
SIGN_HEAT_THRESHOLD = 55
ENDORSEMENT_CAP = 3          # 同一艺人同时生效代言上限
COVER_CAP = 2                # 同一艺人同时排期封面上限
COVER_LEAD_TICKS = 1         # 封面计划于下一 tick 刊登


# 层级权重：决定代言费基准与塌房贬值幅度
TIER_WEIGHT = {
    EndorsementTier.TOP_LUXURY: 1.0,
    EndorsementTier.HIGH_LUXURY: 0.6,
    EndorsementTier.MASS: 0.3,
    EndorsementTier.BRAND_FRIEND: 0.15,
}
TIER_MIN_HEAT = {
    EndorsementTier.TOP_LUXURY: 80,
    EndorsementTier.HIGH_LUXURY: 70,
    EndorsementTier.MASS: 60,
    EndorsementTier.BRAND_FRIEND: 55,
}

# 品牌目录（确定性；annual_fee 单位：万元/年）
BRAND_CATALOG = [
    {"name": "Lumière 顶奢", "category": "腕表", "tier": EndorsementTier.TOP_LUXURY,
     "base_fee": 1200, "penalty_rate": 0.8},
    {"name": "Maison Étoile", "category": "高定", "tier": EndorsementTier.TOP_LUXURY,
     "base_fee": 1000, "penalty_rate": 0.8},
    {"name": "Aqua 护肤", "category": "美妆", "tier": EndorsementTier.HIGH_LUXURY,
     "base_fee": 600, "penalty_rate": 0.6},
    {"name": "Volt 运动", "category": "运动", "tier": EndorsementTier.HIGH_LUXURY,
     "base_fee": 500, "penalty_rate": 0.6},
    {"name": "Daily 饮品", "category": "快消", "tier": EndorsementTier.MASS,
     "base_fee": 200, "penalty_rate": 0.4},
    {"name": "Snack 零嘴", "category": "食品", "tier": EndorsementTier.MASS,
     "base_fee": 150, "penalty_rate": 0.4},
    {"name": "Trend 潮牌", "category": "服饰", "tier": EndorsementTier.BRAND_FRIEND,
     "base_fee": 80, "penalty_rate": 0.3},
]

MAGAZINE_CATALOG = [
    {"name": "VOGUE 风尚", "tier": MagazineTier.TOP5, "base_fee": 300, "prestige": 95},
    {"name": "ELLE 伊人", "tier": MagazineTier.TOP5, "base_fee": 260, "prestige": 90},
    {"name": "BAZAAR 嘉人", "tier": MagazineTier.TOP5, "base_fee": 280, "prestige": 92},
    {"name": "COSMO 都会", "tier": MagazineTier.SECOND_TIER, "base_fee": 120, "prestige": 70},
    {"name": "T 星尚", "tier": MagazineTier.SECOND_TIER, "base_fee": 90, "prestige": 65},
]


# ===================== 纯函数：违约金 / 贬值（可离线单测） =====================
def compute_penalty(annual_fee: int, penalty_rate: float,
                    remaining_ticks: int, duration_ticks: int) -> int:
    """塌房违约金 = 年代言费 × 违约金比例 × 剩余年限占比（封顶 1）。"""
    if duration_ticks <= 0:
        ratio = 1.0
    else:
        ratio = max(0.0, min(1.0, remaining_ticks / duration_ticks))
    return int(round(float(annual_fee) * float(penalty_rate) * ratio))


def commercial_crash_factor(severity: int) -> float:
    """塌房瞬间商业价值贬值系数（severity 越高贬越狠），下限 0.05。"""
    f = 1 - (0.6 + 0.03 * (severity or 5))
    return max(0.05, f)


def tier_weight(tier) -> float:
    return TIER_WEIGHT.get(tier, 0.3)


# ===================== 商业价值读写（列 + attributes 镜像） =====================
def _commercial_value_of(character: Character) -> float:
    cv = getattr(character, "commercial_value", None)
    if cv is not None:
        return float(cv)
    attrs = character.attributes or {}
    if attrs.get("commercial_value") is not None:
        return float(attrs["commercial_value"])
    return float((attrs or {}).get("heat", 50))


def _set_commercial_value(character: Character, value: float):
    character.commercial_value = value
    if character.attributes is None:
        character.attributes = {}
    character.attributes["commercial_value"] = value


# ===================== 桥接 §17.3：塌房违约金（模块函数，供 CrisisAgent 调用） =====================
def apply_collapse_penalty(db: Session, world: World, tick: SimulationTick,
                           character: Character, scandal: Scandal) -> dict:
    """人物塌房时结算商业崩塌（确定性、可重放，无随机）。

    返回结算摘要 dict（供测试/审计/客户端展示）。副作用：
      - 带道德条款的生效代言 → breached + penalty_amount；
      - 商业价值按严重度重挫；
      - 未刊登封面 → terminated（取消）；
      - 写「商业塌房」事件 + world 记忆 sharp_topics(domain=commerce)（复用 §14 媒体闭环）。
    """
    cur = tick.tick_index
    sev = scandal.severity or 5

    # 取该人物全部代言/封面（在 Python 侧按状态过滤，避免复杂 SQL）
    all_endorsements = (
        db.query(Endorsement).filter(
            Endorsement.world_id == world.id,
            Endorsement.character_id == character.id,
        ).all()
    )
    active_morals = [e for e in all_endorsements
                     if e.status == ContractStatus.ACTIVE and e.has_morals_clause]

    breaches = []
    total_penalty = 0
    for c in active_morals:
        remaining = max(0, c.duration_ticks - (cur - c.signed_tick))
        pen = compute_penalty(c.annual_fee, c.penalty_rate, remaining, c.duration_ticks)
        c.status = ContractStatus.BREACHED
        c.terminated_tick = cur
        c.penalty_amount = pen
        total_penalty += pen
        breaches.append({"brand": c.brand_name, "penalty": pen,
                         "tier": c.tier.value if hasattr(c.tier, "value") else str(c.tier)})

    # 商业价值重挫
    cv_before = _commercial_value_of(character)
    cv_after = int(round(cv_before * commercial_crash_factor(sev)))
    _set_commercial_value(character, cv_after)

    # 取消未刊登封面
    all_covers = (
        db.query(MagazineCover).filter(
            MagazineCover.world_id == world.id,
            MagazineCover.character_id == character.id,
        ).all()
    )
    cancelled = []
    for cov in all_covers:
        if cov.status == ContractStatus.ACTIVE and cov.issue_tick > cur:
            cov.status = ContractStatus.TERMINATED
            cov.cancelled_tick = cur
            cancelled.append(cov.magazine_name)

    # 事件（媒体闭环即时消费）
    db.add(Event(
        world_id=world.id, tick_id=tick.id,
        event_date=tick.to_date.date() if tick.to_date else None,
        level=EventLevel.HISTORIC, category="商业",
        title=f"{character.name} 商业帝国崩塌",
        description=(f"因{_scandal_type_label(scandal)}塌房，"
                     f"{len(breaches)} 个代言解约违约，赔付违约金约 {total_penalty} 万；"
                     f"商业价值由 {int(cv_before)} 重挫至 {cv_after}"
                     + (f"；{len(cancelled)} 个封面排期取消" if cancelled else "")),
        causal_chain={"scandal_id": scandal.id, "character_id": character.id,
                      "breaches": len(breaches), "total_penalty": total_penalty,
                      "commercial_value_before": int(cv_before),
                      "commercial_value_after": cv_after},
        affected_entities=[{"type": "character", "id": character.id},
                           {"type": "scandal", "id": scandal.id}],
    ))

    # 复用 §14：sharp_topics(domain=commerce) → 媒体 Agent 下一 tick 生成争议通稿
    _emit_sharp(db, world, cur, character, scandal, total_penalty)

    # 长期记忆（供 §17.2/媒体注脚未来读取）
    store = MemoryStore(db, world)
    store.write_long(
        "character_agent", f"char:{character.id}:commercial",
        value={"collapsed": True, "total_penalty": total_penalty,
               "commercial_value_after": cv_after, "scandal_id": scandal.id},
        importance=0.8,
    )

    return {
        "character_id": character.id,
        "breaches": breaches,
        "total_penalty": total_penalty,
        "commercial_value_before": int(cv_before),
        "commercial_value_after": cv_after,
        "cancelled_covers": cancelled,
    }


def _scandal_type_label(scandal: Scandal) -> str:
    labels = {
        "affair": "出轨", "drugs": "吸毒", "tax": "税务", "slip_of_tongue": "言论",
        "surrogacy": "代孕", "plagiarism": "抄袭", "domestic_violence": "家暴",
        "other": "争议",
    }
    t = scandal.scandal_type
    key = t.value if hasattr(t, "value") else str(t)
    return labels.get(key, "争议")


def _emit_sharp(db, world, cur, character, scandal, total_penalty):
    store = MemoryStore(db, world)
    mem = store.recall_one("world", MemoryScope.WORLD, "sharp_topics")
    topics = mem.value if mem and isinstance(mem.value, list) else []
    topics.append({
        "headline": f"商业塌房：{character.name} 代言集体解约，赔付违约金约 {total_penalty} 万",
        "scandal_id": scandal.id,
        "character_id": character.id,
        "domain": "commerce",
        "created_tick": cur,
        "consumed": False,
    })
    store.write_world("sharp_topics", topics, importance=0.95)


# ===================== CommercialAgent =====================
class CommercialAgent:
    """每 tick 维护人物商业价值，并为高热度艺人确定性地接洽代言/封面。"""

    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick

    def run(self) -> int:
        characters = (
            self.db.query(Character).filter(
                Character.world_id == self.world.id,
                Character.status == CharacterStatus.ACTIVE,
                Character.type.in_(CELEB_TYPES),
            ).all()
        )
        for c in characters:
            self._ensure_init(c)
            if self._is_collapsed(c):
                continue  # 已塌房人物不再接新商务
            self._maybe_sign(c)
            self._maybe_cover(c)
        self.db.flush()
        return len(characters)

    # ---------- 初始化 / 状态 ----------
    def _ensure_init(self, c: Character):
        if getattr(c, "commercial_value", None) is None:
            attrs = c.attributes or {}
            base = float(attrs.get("heat", 50))
            _set_commercial_value(c, int(round(base)))

    def _is_collapsed(self, c: Character) -> bool:
        rows = (
            self.db.query(Scandal).filter(
                Scandal.world_id == self.world.id,
                Scandal.character_id == c.id,
            ).all()
        )
        return any(r.stage == ScandalStage.COLLAPSED for r in rows)

    # ---------- 确定性签约 ----------
    def _maybe_sign(self, c: Character):
        active = [
            e for e in self.db.query(Endorsement).filter(
                Endorsement.world_id == self.world.id,
                Endorsement.character_id == c.id,
            ).all() if e.status == ContractStatus.ACTIVE
        ]
        if len(active) >= ENDORSEMENT_CAP:
            return
        held = {e.brand_name for e in active}
        heat = int((c.attributes or {}).get("heat", 50))
        if heat < SIGN_HEAT_THRESHOLD:
            return
        for idx, brand in enumerate(BRAND_CATALOG):
            if brand["name"] in held:
                continue
            tier = brand["tier"]
            tier_min = TIER_MIN_HEAT[tier]
            if heat < tier_min:
                continue
            # 确定性倾向：人气越高越易签；id×tick×brand 扰动保证可重放且分散
            propensity = (heat - tier_min) + ((c.id + self.tick.tick_index + idx) % 9) - 4
            if propensity >= 6:
                self._sign(c, brand, heat)
                break  # 每 tick 至多签 1 个

    def _sign(self, c: Character, brand: dict, heat: int):
        fee = int(round(brand["base_fee"] * (0.5 + heat / 100.0)))
        self.db.add(Endorsement(
            world_id=self.world.id, character_id=c.id,
            brand_name=brand["name"], category=brand["category"], tier=brand["tier"],
            annual_fee=fee, penalty_rate=brand["penalty_rate"], has_morals_clause=True,
            signed_tick=self.tick.tick_index, duration_ticks=12,
            status=ContractStatus.ACTIVE,
        ))

    def _maybe_cover(self, c: Character):
        active = [
            cov for cov in self.db.query(MagazineCover).filter(
                MagazineCover.world_id == self.world.id,
                MagazineCover.character_id == c.id,
            ).all() if cov.status == ContractStatus.ACTIVE
        ]
        if len(active) >= COVER_CAP:
            return
        heat = int((c.attributes or {}).get("heat", 50))
        if heat < 65:
            return
        held = {cov.magazine_name for cov in active}
        for idx, mag in enumerate(MAGAZINE_CATALOG):
            if mag["name"] in held:
                continue
            tier_min = 80 if mag["tier"] == MagazineTier.TOP5 else 65
            if heat < tier_min:
                continue
            propensity = (heat - tier_min) + ((c.id + self.tick.tick_index + idx) % 7) - 3
            if propensity >= 5:
                self._cover(c, mag)
                break

    def _cover(self, c: Character, mag: dict):
        fee = int(round(mag["base_fee"] * (0.5 + ((c.attributes or {}).get("heat", 50)) / 100.0)))
        self.db.add(MagazineCover(
            world_id=self.world.id, character_id=c.id,
            magazine_name=mag["name"], tier=mag["tier"],
            issue_tick=self.tick.tick_index + COVER_LEAD_TICKS,
            theme="封面人物", fee=fee, prestige=mag["prestige"],
            status=ContractStatus.ACTIVE,
        ))
