"""§17.2 人际情感网络 Agent：恋情 / 绯闻 / 结婚生子 · 粉丝蝴蝶效应。

底层逻辑（确定性、可重放、无随机）：
  1. 编排：情感关系由玩家（GM/运营，relationship:manage 权限）经 Intervention 审计创建；
     可立即公开（is_public）或先地下（publicness 随 tick 自然泄露）。
  2. 粉丝蝴蝶效应：关系公开瞬间，按人物「偶像依赖度(idol_appeal)」确定性结算
     应援(支持) vs 脱粉回踩(脱粉+反噬) 的舆论走向——偶像型(歌手/小花)依赖单身红利，
     公开恋情/结婚/生子 → 大幅脱粉、甚至被回踩；成熟型艺人影响温和。
  3. 与 §17.3 强耦合：一方卷入「出轨(affair)」丑闻（SPREADING/ERUPTED/COLLAPSED）
     时，本关系自动结束（分手/离婚），并触发该方脱粉——「黑料(§17.3) → 情感崩塌(§17.2)」。
  4. 无缝复用 §14 闭环：公开恋情 / 回踩等写「情感争议」事件（媒体当 tick 生成 CONTROVERSY 新闻）
     + 世界记忆 sharp_topics(domain=relationship)，媒体 Agent 下一 tick 自动生成争议通稿（零改动）。

所有数值结算均为纯函数（无 DB、无随机），便于审计、单测与可重放。
"""
from typing import Optional

from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.event import Event
from app.models.enums import EventLevel, CharacterType, CharacterStatus, MemoryScope, RomanceStatus
from app.models.character import Character
from app.models.romance import Romance
from app.models.crisis import Scandal, ScandalStage, ScandalType
from app.sim.memory import MemoryStore


# ===================== 确定性超参（可重放） =====================
# 各类型艺人的「偶像依赖度」基准：越高越依赖单身/CP 红利，公开情感越易脱粉。
IDOL_APPEAL_BY_TYPE = {
    CharacterType.SINGER: 75,     # 歌手/偶像：单身红利最高
    CharacterType.ACTOR: 40,      # 演员：中等
    CharacterType.DIRECTOR: 30,
    CharacterType.WRITER: 30,
    CharacterType.PRODUCER: 25,
    CharacterType.CINEMATOGRAPHER: 25,
    CharacterType.EDITOR: 25,
    CharacterType.COMPOSER: 45,   # 音乐人：偏偶像
    CharacterType.AGENT: 20,
    CharacterType.EXECUTIVE: 20,
}
# 曝光自然泄露速率（每 tick 公开度增量）
LEAK_PER_TICK = 6
# 触发自动公开的公开度阈值
PUBLIC_THRESHOLD = 60
# 关系稳定多少 tick 后允许"生子"（避免刚恋爱就生）
CHILD_MIN_TICKS = 12


# ===================== 纯函数：粉丝蝴蝶效应（可离线单测） =====================
def fan_profile(character: Character) -> dict:
    """返回该人物的粉丝结构画像（确定性，来自 type + attributes 覆盖）。"""
    base = IDOL_APPEAL_BY_TYPE.get(character.type, 35)
    attrs = character.attributes or {}
    # attributes 可显式覆盖（如某演员刻意经营"少女偶像"人设）
    override = attrs.get("idol_appeal")
    idol_appeal = int(override) if isinstance(override, (int, float)) else int(base)
    idol_appeal = max(0, min(100, idol_appeal))
    # 单人梦碎脱粉比例（粉丝中"为单身/CP 买单"的比例）
    solo_share = int(round(idol_appeal * 0.6))
    # 伴侣/CP 支持比例（相对稳健的受众）
    cp_share = 100 - solo_share
    return {"idol_appeal": idol_appeal, "solo_share": solo_share, "cp_share": cp_share}


def compute_fan_reaction(profile: dict, romance_type, is_public: bool,
                         confirmed: bool = True) -> dict:
    """确定性结算公开情感关系对粉丝群体的冲击（heat/opinion 增量，全来自画像与类型）。

    返回 {heat_delta, opinion_delta, defect, support, backstab, note}。纯函数。
    - 绯闻(rumor)未实锤：仅制造话题热度（buzz），不触发脱粉；实锤后按恋情处理。
    - 恋情/结婚/生子：偶像依赖度越高，脱粉越狠；成熟型影响温和甚至小幅应援。
    - 回踩(backstab)：偶像依赖度极高且"毫无铺垫突然公开"时，单人粉反噬（额外口碑下滑）。
    """
    idol = profile["idol_appeal"]
    solo = profile["solo_share"]
    cp = profile["cp_share"]

    # 绯闻：注意力经济，热度高涨但口碑中性；未实锤不脱粉
    if romance_type == "rumor" and not confirmed:
        buzz = int(round(6 + idol * 0.06))
        return {"heat_delta": buzz, "opinion_delta": 0, "defect": 0, "support": 0,
                "backstab": False,
                "note": f"绯闻未坐实，话题度+{buzz}（吃瓜围观，暂无脱粉）"}

    # 关系类型权重：结婚/生子比单纯恋情冲击更大（承诺感更强）
    type_weight = {
        "dating": 1.0,
        "cohabit": 1.1,
        "married": 1.4,
        "rumor": 1.0,   # 实锤绯闻等同恋情
    }.get(romance_type, 1.0)

    # 脱粉：偶像依赖度越高，单人粉梦碎越多
    defect = int(round(solo * 0.5 * type_weight))
    # 应援：CP粉/稳健受众的轻微正向（婚礼/新生儿常被祝福）
    support = int(round(cp * 0.12 * type_weight))
    # 回踩：偶像依赖度极高（>=70）且毫无铺垫突然公开 → 反噬
    backstab = idol >= 70
    backstab_hit = int(round(idol * 0.15)) if backstab else 0

    heat_delta = support - defect
    opinion_delta = -backstab_hit  # 回踩拉低口碑；否则中性
    note = (f"偶像依赖度{idol}：脱粉约{defect}、应援+{support}"
            + (f"、遭回踩口碑-{backstab_hit}" if backstab else ""))
    return {"heat_delta": heat_delta, "opinion_delta": opinion_delta,
            "defect": defect, "support": support, "backstab": backstab, "note": note}


def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(v))))


# ===================== RomanceAgent =====================
class RomanceAgent:
    """每个 tick 演化本世界情感关系：自然曝光、§17.3 出轨拆散、粉丝蝴蝶效应结算。"""

    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick
        self.store = MemoryStore(db, world)

    def run(self) -> int:
        active = (
            self.db.query(Romance).filter(
                Romance.world_id == self.world.id,
                Romance.status == RomanceStatus.ACTIVE,
            ).all()
        )
        processed = 0
        for r in active:
            # 1) §17.3 桥接：一方出轨丑闻 → 关系结束（分手/离婚）
            if self._affair_breaks(r):
                self._end_romance(r, "因一方出轨丑闻拆散", backstab_party=self._other_party_in_affair(r))
                processed += 1
                continue
            # 2) 自然曝光：地下关系 publicness 累积，达阈值自动公开并结算蝴蝶效应
            if not r.is_public:
                r.publicness = min(100, r.publicness + LEAK_PER_TICK)
                if r.publicness >= PUBLIC_THRESHOLD:
                    self._reveal(r, auto=True)
                    processed += 1
                    continue
            # 3) 已公开且未结算 → 结算一次粉丝蝴蝶效应（兜底，正常由 reveal 触发）
            if r.is_public and r.reacted_tick is None:
                self._apply_reaction(r, f"{_type_label(r.romance_type)}公开")
                processed += 1
        self.db.flush()
        return processed

    # ---------- §17.3 桥接 ----------
    def _affair_breaks(self, r: Romance) -> bool:
        """任一方卷入「出轨」丑闻（已曝光/爆发/塌房）且尚未结算 → 应拆散。"""
        if r.reacted_tick is not None and r.ended_tick is not None:
            return False
        partners = [r.character_a_id, r.character_b_id]
        rows = (
            self.db.query(Scandal).filter(
                Scandal.world_id == self.world.id,
                Scandal.character_id.in_(partners),
                Scandal.scandal_type == ScandalType.AFFAIR,
                Scandal.stage.in_([ScandalStage.SPREADING, ScandalStage.ERUPTED,
                                   ScandalStage.COLLAPSED]),
            ).all()
        )
        return len(rows) > 0

    def _other_party_in_affair(self, r: Romance):
        """返回卷入出轨的一方 id（用于脱粉归因）。"""
        partners = [r.character_a_id, r.character_b_id]
        rows = (
            self.db.query(Scandal).filter(
                Scandal.world_id == self.world.id,
                Scandal.character_id.in_(partners),
                Scandal.scandal_type == ScandalType.AFFAIR,
                Scandal.stage.in_([ScandalStage.SPREADING, ScandalStage.ERUPTED,
                                   ScandalStage.COLLAPSED]),
            ).all()
        )
        return rows[0].character_id if rows else None

    # ---------- 公开 / 结算 ----------
    def _reveal(self, r: Romance, auto: bool):
        r.is_public = True
        self._apply_reaction(r, f"{_type_label(r.romance_type)}公开" + ("（自然泄露）" if auto else "（官宣）"))

    def _apply_reaction(self, r: Romance, event_title: str):
        """结算粉丝蝴蝶效应：更新双方 heat/opinion、写事件 + sharp_topics（复用 §14）。"""
        cur = self.tick.tick_index
        r.reacted_tick = cur
        partners = [r.character_a_id, r.character_b_id]
        backstab_any = False
        for cid in partners:
            char = self.db.get(Character, cid)
            if char is None or char.status != CharacterStatus.ACTIVE:
                continue
            prof = fan_profile(char)
            res = compute_fan_reaction(prof, r.romance_type, True, confirmed=True)
            heat = int((char.attributes or {}).get("heat", 50))
            new_heat = _clamp(heat + res["heat_delta"])
            attrs = dict(char.attributes or {})
            attrs["heat"] = new_heat
            char.attributes = attrs
            backstab_any = backstab_any or res["backstab"]
            # 属性变更留痕（可追溯，防失真）
            self.db.add(_attr_log(char, self.tick, heat, new_heat,
                                  f"情感网络演化：{res['note']}"))
            # §17.1 桥接：脱粉 → 商业价值随人气下滑而贬损（双写镜像）
            self._maybe_depress_commercial(char, new_heat)
        # 媒体事件（当 tick 生成 CONTROVERSY 新闻）
        self._emit_event(r, event_title, backstab_any)
        # 复用 §14：sharp_topics(domain=relationship) → 媒体下一 tick 争议通稿
        self._emit_sharp(r, cur, backstab_any)

    def _maybe_depress_commercial(self, char: Character, new_heat: int):
        """脱粉导致人气下滑，商业价值镜像贬值（与 §17.1 同源口径：以 heat 为代理）。"""
        try:
            from app.sim.commerce_agent import _commercial_value_of, _set_commercial_value
        except Exception:
            return
        cv = _commercial_value_of(char)
        # 商业价值与人气正相关（确定性线性映射，下限 0）
        target = max(0, int(round(new_heat * (cv / max(1, int((char.attributes or {}).get('heat', 50)) or 1)))))
        if target < cv:
            _set_commercial_value(char, target)

    # ---------- 结束关系 ----------
    def _end_romance(self, r: Romance, reason: str, backstab_party: Optional[int] = None):
        cur = self.tick.tick_index
        r.status = RomanceStatus.ENDED
        r.ended_tick = cur
        r.ended_reason = reason
        # 分手/离婚：出轨方额外脱粉（回踩）
        if backstab_party is not None:
            char = self.db.get(Character, backstab_party)
            if char is not None and char.status == CharacterStatus.ACTIVE:
                heat = int((char.attributes or {}).get("heat", 50))
                new_heat = _clamp(heat - 8)
                attrs = dict(char.attributes or {})
                attrs["heat"] = new_heat
                char.attributes = attrs
                self.db.add(_attr_log(char, self.tick, heat, new_heat,
                                      f"情感崩塌：因出轨丑闻致关系结束，脱粉-{8}"))
        self._emit_event(r, f"{_type_label(r.romance_type)}结束：{reason}", backstab=True)
        self._emit_sharp(r, cur, backstab=True, ending=True)

    # ---------- 复用 §14 闭环的写入函数 ----------
    def _emit_event(self, r: Romance, title: str, backstab: bool):
        partners = [r.character_a_id, r.character_b_id]
        self.db.add(Event(
            world_id=self.world.id, tick_id=self.tick.id,
            event_date=self.tick.to_date.date() if self.tick.to_date else None,
            level=EventLevel.MAJOR if backstab else EventLevel.IMPORTANT,
            category="情感争议",
            title=title,
            description=(f"{_name(self.db, r.character_a_id)} 与 "
                         f"{_name(self.db, r.character_b_id)} 的"
                         f"{_type_label(r.romance_type)}引发粉丝"
                         f"{'回踩脱粉' if backstab else '热议'}"),
            causal_chain={"romance_id": r.id, "romance_type": r.romance_type.value,
                          "is_public": r.is_public, "child_count": r.child_count},
            affected_entities=[{"type": "character", "id": p} for p in partners],
        ))

    def _emit_sharp(self, r: Romance, cur: int, backstab: bool, ending: bool = False):
        store = self.store
        mem = store.recall_one("world", MemoryScope.WORLD, "sharp_topics")
        topics = getattr(mem, "value", None)
        topics = topics if isinstance(topics, list) else []
        if ending:
            headline = (f"情感地震：{_name(self.db, r.character_a_id)} 与 "
                        f"{_name(self.db, r.character_b_id)} 因丑闻分手")
        elif backstab:
            headline = (f"回踩现场：{_name(self.db, r.character_a_id)} 公开"
                        f"{_type_label(r.romance_type)}，单人粉脱粉反噬")
        else:
            headline = f"情感动态：{_name(self.db, r.character_a_id)} 公开{_type_label(r.romance_type)}"
        topics.append({
            "headline": headline,
            "romance_id": r.id,
            "domain": "relationship",
            "created_tick": cur,
            "consumed": False,
        })
        store.write_world("sharp_topics", topics, importance=0.9)


# ===================== 模块级工具（供 API 端点复用以保持逻辑单一来源） =====================
def apply_romance_reaction(db: Session, world: World, tick: SimulationTick,
                           romance: Romance, event_title: str) -> dict:
    """公开/生子/结束等动作在非 tick 上下文发起时，复用同一确定性结算（见 RomanceAgent._apply_reaction）。"""
    agent = RomanceAgent(db, world, tick)
    before = {cid: int((db.get(Character, cid).attributes or {}).get("heat", 50))
              for cid in (romance.character_a_id, romance.character_b_id)}
    agent._apply_reaction(romance, event_title)
    after = {cid: int((db.get(Character, cid).attributes or {}).get("heat", 50))
             for cid in (romance.character_a_id, romance.character_b_id)}
    return {"before": before, "after": after}


def _type_label(t) -> str:
    return {
        "dating": "恋情", "rumor": "绯闻", "married": "婚讯", "cohabit": "同居",
    }.get(t.value if hasattr(t, "value") else str(t), "恋情")


def _name(db: Session, cid: int) -> str:
    c = db.get(Character, cid)
    return c.name if c else f"人物{cid}"


def _attr_log(char: Character, tick: SimulationTick, old: int, new: int, reason: str):
    from app.models.character import CharacterAttributeLog
    return CharacterAttributeLog(
        character_id=char.id, tick_id=tick.id, field="heat",
        old_value={"heat": old}, new_value={"heat": new}, reason=reason,
    )
