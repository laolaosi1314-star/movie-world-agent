"""§17.3 舆论与危机公关 Agent：黑料爆料 · 丑闻演化 · 多阶段公关。

底层逻辑（确定性、可重放、无随机）：
  1. 黑料爆料：Scandal 由玩家（GM/运营，crisis:manage 权限）经 Intervention 审计创建；
     可立即曝光（SPREADING）或先潜伏（LATENT）待后续曝光。
  2. 丑闻演化：每 tick 推进状态机 LATENT→SPREADING→ERUPTED→(RESOLVING)→RESOLVED/COLLAPSED，
     舆情热度/口碑按确定性曲线升降；实锤+严重+口碑见底 → 塌房（不可逆）。
  3. 多阶段公关：evaluate_pr 以「动作 × 严重度 × 证据强度 × 是否实锤」确定性结算
     舆论恢复曲线（冷处理/律师函/道歉/买热搜/洗白反转各有胜负手）。

无缝复用 §14 闭环（不改动媒体 Agent）：
  - 爆发/关键节点产「丑闻争议」事件 → 媒体 Agent 按 category 含"争议"路由为 CONTROVERSY 新闻；
  - 同时把话题写入世界记忆 sharp_topics → 媒体 Agent 在后续 tick 自动生成争议通稿（与负面奖项同源）；
  - 塌房/平息写入 char:{id}:notorious 长期记忆 → §14.3 媒体背景注脚自然带出"曾因丑闻塌房"；
  - scandal_reputation_penalty() 直接喂入 AwardAgent._badness，使丑闻缠身者更易被金酸梅点名。
"""
from typing import Optional

from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.event import Event
from app.models.enums import (
    EventLevel, ScandalType, ScandalStage, PRStrategy, MemoryScope,
)
from app.models.crisis import Scandal, CrisisPR
from app.models.character import Character
from app.sim.memory import MemoryStore
from app.sim.commerce_agent import apply_collapse_penalty  # §17.1 塌房违约金桥接


# ===================== 确定性超参（可重放） =====================
HEAT_DECAY_PER_TICK = 0.85     # 每 tick 热度乘性衰减系数
HEAT_CALM = 25                 # 热度低于此值，公众开始"遗忘"→口碑回升
RECOVERY_RATE = 2              # 平静时口碑每 tick 回升/回落点数
SPREAD_TICKS_TO_ERUPT = 2      # 发酵多少个 tick 后爆发
COLLAPSE_OPINION = 5           # 口碑低于此值且实锤严重 → 塌房
RESOLVE_QUIET_TICKS = 3        # 热度归零持续多少 tick → 平息


def clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(v))))


SCANDAL_TYPE_LABELS = {
    ScandalType.AFFAIR: "出轨",
    ScandalType.DRUGS: "吸毒",
    ScandalType.TAX: "税务问题",
    ScandalType.SLIP_OF_TONGUE: "言论翻车",
    ScandalType.SURROGACY: "代孕",
    ScandalType.PLAGIARISM: "抄袭",
    ScandalType.DOMESTIC_VIOLENCE: "家暴",
    ScandalType.OTHER: "争议",
}

PR_STRATEGY_LABELS = {
    PRStrategy.COLD_TREATMENT: "冷处理",
    PRStrategy.LAWYER_LETTER: "发律师函",
    PRStrategy.APOLOGY: "公开道歉",
    PRStrategy.BUY_TRENDING: "买热搜",
    PRStrategy.COUNTER_MKT: "反向营销/洗白反转",
}


# ===================== 纯函数：公关结算（可离线单测） =====================
# 各策略基础效果（severity 进一步缩放）。注释即设计意图，全部确定性。
PR_PROFILES = {
    PRStrategy.COLD_TREATMENT: {
        "heat": -10, "opinion": 0, "recovery_boost": True,
        "confirmed_penalty": -3,
        "note": "冷处理：不回应，热度自然冷却；实锤仍装死公众不满",
    },
    PRStrategy.LAWYER_LETTER: {
        "heat": -14, "opinion": 2,
        "weak_evidence_bonus": 5,    # 证据弱（被诬陷）→ 维权成功加分
        "confirmed_penalty": -7,     # 实锤还发函"捂嘴"→ 公众反感
        "note": "律师函：威慑降温；证据弱时奏效，实锤时像捂嘴",
    },
    PRStrategy.APOLOGY: {
        "heat": -5, "opinion": 6,
        "confirmed_bonus": 4,        # 实锤认错 → 公众接受
        "unconfirmed_backfire": -9,  # 未实锤却道歉 = 变相认锤
        "note": "道歉：实锤时认错加分；未实锤时像此地无银",
    },
    PRStrategy.BUY_TRENDING: {
        "heat": -12, "opinion": -1, "decay_only": True,
        "confirmed_penalty": -5,     # 实锤买热搜盖 = 强行洗地
        "note": "买热搜：短期压热度，口碑略负；随后热度反弹",
    },
    PRStrategy.COUNTER_MKT: {
        "heat": -7, "opinion": 10,
        "weak_evidence_bonus": 9,    # 证据弱 → 成功洗白反转
        "confirmed_penalty": -12,    # 实锤强行洗白 → 塌房加速
        "note": "反向营销/洗白：证据弱可大翻盘，实锤遭群嘲",
    },
}


def evaluate_pr(strategy: PRStrategy, severity: int, evidence: int,
                is_confirmed: bool, stage=None) -> dict:
    """确定性公关结算：返回本动作对热度/口碑的增量与可解释说明。

    纯函数（无 DB、无随机），便于审计、单测与可重放。
    """
    prof = PR_PROFILES[strategy]
    sev_scale = 0.6 + (severity or 5) / 25.0   # 1-10 → 0.64..1.0
    delta_heat = int(round(prof["heat"] * sev_scale))
    delta_opinion = int(round(prof["opinion"] * sev_scale))
    notes = [prof["note"]]

    if not is_confirmed and prof.get("weak_evidence_bonus"):
        b = int(round(prof["weak_evidence_bonus"] * sev_scale))
        delta_opinion += b
        notes.append(f"证据弱(强度{evidence})→加分{b}")
    if is_confirmed and prof.get("confirmed_penalty"):
        p = int(round(prof["confirmed_penalty"] * sev_scale))
        delta_opinion += p
        notes.append(f"已实锤→反感{p}")
    if is_confirmed and prof.get("confirmed_bonus"):
        b = int(round(prof["confirmed_bonus"] * sev_scale))
        delta_opinion += b
        notes.append(f"实锤认错→加分{b}")
    if not is_confirmed and prof.get("unconfirmed_backfire"):
        b = int(round(prof["unconfirmed_backfire"] * sev_scale))
        delta_opinion += b
        notes.append(f"未实锤却道歉→变相认锤{b}")

    return {
        "delta_heat": delta_heat,
        "delta_opinion": delta_opinion,
        "recovery_boost": prof.get("recovery_boost", False),
        "decay_only": prof.get("decay_only", False),
        "note": "；".join(notes),
    }


def compute_eruption_drop(severity: int, evidence: int, is_confirmed: bool) -> int:
    """爆发瞬间的口碑重创（确定性）。"""
    drop = (severity or 5) * 2 + (evidence or 5) + (12 if is_confirmed else 0)
    return min(60, drop)


def natural_recovery_target(severity: int) -> int:
    """平静后口碑回归基线：越严重的丑闻越难完全恢复。"""
    return max(8, 50 - (severity or 5) * 2)


# ===================== 桥接 §14 _badness（负面奖项更易点名丑闻人物） =====================
def scandal_reputation_penalty(db: Session, world: World, character_id: int) -> float:
    """返回该人物的"劣迹加成"（喂入 AwardAgent._badness 的负数侧）。

    仅统计「已曝光且实锤」的活跃丑闻；无数据/表不可用时安全返回 0.0。
    """
    try:
        rows = (
            db.query(Scandal).filter(
                Scandal.world_id == world.id,
                Scandal.character_id == character_id,
                Scandal.stage.in_([
                    ScandalStage.SPREADING, ScandalStage.ERUPTED,
                    ScandalStage.RESOLVING, ScandalStage.COLLAPSED,
                ]),
                Scandal.is_confirmed.is_(True),
            ).all()
        )
    except Exception:
        return 0.0
    pen = 0.0
    for s in rows:
        opinion_gap = max(0, 50 - (s.public_opinion or 50))
        pen += opinion_gap * 0.4 + (s.severity or 5) * 0.5
    return pen


# ===================== CrisisAgent =====================
class CrisisAgent:
    """每个 tick 演化本世界所有活跃丑闻，并把话题/事件喂入 §14 媒体闭环。"""

    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick

    def run(self) -> int:
        active = (
            self.db.query(Scandal).filter(
                Scandal.world_id == self.world.id,
                Scandal.stage.in_([
                    ScandalStage.LATENT, ScandalStage.SPREADING,
                    ScandalStage.ERUPTED, ScandalStage.RESOLVING,
                ]),
            ).all()
        )
        for s in active:
            self._evolve(s)
        self.db.flush()
        return len(active)

    # ---------- 演化核心 ----------
    def _evolve(self, s: Scandal):
        cur = self.tick.tick_index
        # 自然降温（乘性衰减 + 固定回落，确定性）
        s.heat = max(0, int(s.heat * HEAT_DECAY_PER_TICK) - 1)

        if s.stage == ScandalStage.LATENT:
            # 潜伏：内部小范围流传，热度极缓上升但不公开
            s.heat = min(100, s.heat + 1)
            return

        if s.stage == ScandalStage.SPREADING:
            age = (cur - s.exposed_tick) if s.exposed_tick is not None else 0
            if age >= SPREAD_TICKS_TO_ERUPT:
                self._erupt(s, cur)
            else:
                s.heat = min(100, s.heat + 2)
                s.public_opinion = max(0, s.public_opinion - max(1, (s.severity or 5) // 4))
            return

        if s.stage == ScandalStage.ERUPTED:
            s.public_opinion = max(0, s.public_opinion - max(1, (s.severity or 5) // 3))
            self._maybe_terminal(s, cur)
            return

        if s.stage == ScandalStage.RESOLVING:
            self._recover(s)
            self._maybe_terminal(s, cur)
            return

    def _erupt(self, s: Scandal, cur: int):
        drop = compute_eruption_drop(s.severity, s.evidence_strength, s.is_confirmed)
        s.public_opinion = max(0, s.public_opinion - drop)
        s.heat = min(100, s.heat + 20)
        s.stage = ScandalStage.ERUPTED
        s.erupted_tick = cur
        self._emit_event(s, EventLevel.MAJOR, "丑闻争议",
                         f"{s.title} 引爆",
                         f"{SCANDAL_TYPE_LABELS.get(s.scandal_type, '争议')}曝光/实锤，舆论哗然")
        self._emit_sharp(s, cur)   # 复用 §14 sharp_topics → 争议通稿

    def _recover(self, s: Scandal):
        target = natural_recovery_target(s.severity)
        if s.heat <= HEAT_CALM:
            if s.public_opinion < target:
                s.public_opinion = min(target, s.public_opinion + RECOVERY_RATE)
            elif s.public_opinion > target:
                s.public_opinion = max(target, s.public_opinion - RECOVERY_RATE)

    def _maybe_terminal(self, s: Scandal, cur: int):
        # 塌房：实锤 + 严重 + 口碑见底（不可逆）
        if (s.is_confirmed and (s.severity or 5) >= 8
                and s.public_opinion <= COLLAPSE_OPINION):
            s.stage = ScandalStage.COLLAPSED
            s.resolved_tick = cur
            self._write_reputation_memory(s, collapsed=True)
            self._emit_event(s, EventLevel.HISTORIC, "丑闻争议",
                             f"{s.title} 塌房", "身败名裂，事业遭受重创")
            # §17.1 桥接：塌房 → 真金白银的商业崩塌（代言违约+违约金+商业价值重挫+封面取消）
            char = self.db.get(Character, s.character_id)
            if char is not None:
                apply_collapse_penalty(self.db, self.world, self.tick, char, s)
            return
        # 平息：热度归零并稳定若干 tick
        if s.heat == 0:
            if s.resolved_tick is None:
                s.resolved_tick = cur
            elif (cur - s.resolved_tick) >= RESOLVE_QUIET_TICKS:
                s.stage = ScandalStage.RESOLVED
                self._write_reputation_memory(s, collapsed=False)
                self._emit_event(s, EventLevel.IMPORTANT, "丑闻争议",
                                 f"{s.title} 平息", "风波渐息，舆论回归平稳")

    # ---------- 公关动作（玩家经 Intervention 审计调用） ----------
    def apply_pr(self, scandal: Scandal, strategy: PRStrategy,
                 by_player_id: Optional[str], note: Optional[str]) -> CrisisPR:
        res = evaluate_pr(strategy, scandal.severity, scandal.evidence_strength,
                          scandal.is_confirmed, scandal.stage)
        scandal.heat = clamp(scandal.heat + res["delta_heat"])
        scandal.public_opinion = clamp(scandal.public_opinion + res["delta_opinion"])
        # 买热搜：短期压热度但随后反弹（确定性补偿）
        if res.get("decay_only"):
            scandal.heat = clamp(scandal.heat + 6)
        # 进入处理中（已塌房/平息则公关无效但留痕）
        if scandal.stage in (ScandalStage.SPREADING, ScandalStage.ERUPTED,
                             ScandalStage.RESOLVING):
            scandal.stage = ScandalStage.RESOLVING

        rec = CrisisPR(
            world_id=scandal.world_id, scandal_id=scandal.id,
            strategy=strategy, by_player_id=by_player_id,
            impact=res, note=note,
        )
        self.db.add(rec)
        self.db.flush()
        # 公关动作本身成为媒体行业动态（可被报道）
        self._emit_event(scandal, EventLevel.IMPORTANT, "行业",
                         f"公关动作：{PR_STRATEGY_LABELS.get(strategy, '公关')}",
                         note or "团队启动危机公关")
        return rec

    # ---------- 复用 §14 闭环的写入函数 ----------
    def _emit_sharp(self, s: Scandal, cur: int):
        """把丑闻话题写入世界记忆 sharp_topics（与负面奖项同源，媒体 Agent 下一 tick 消费）。"""
        store = MemoryStore(self.db, self.world)
        mem = store.recall_one("world", MemoryScope.WORLD, "sharp_topics")
        topics = mem.value if mem and isinstance(mem.value, list) else []
        topics.append({
            "headline": f"丑闻：{s.title}（{SCANDAL_TYPE_LABELS.get(s.scandal_type, '争议')}）",
            "scandal_id": s.id,
            "domain": "crisis",
            "created_tick": cur,
            "consumed": False,
        })
        store.write_world("sharp_topics", topics, importance=0.95)

    def _emit_event(self, s: Scandal, level: EventLevel, category: str,
                    title: str, description: str):
        self.db.add(Event(
            world_id=self.world.id, tick_id=self.tick.id,
            event_date=self.tick.to_date.date(), level=level,
            category=category, title=title, description=description,
            causal_chain={"scandal_id": s.id, "scandal_type": s.scandal_type.value,
                          "stage": s.stage.value, "heat": s.heat,
                          "public_opinion": s.public_opinion},
            affected_entities=[{"type": "character", "id": s.character_id},
                                {"type": "scandal", "id": s.id}],
        ))

    def _write_reputation_memory(self, s: Scandal, collapsed: bool):
        """复用 §14.3 的 notorious 注脚键 + 新增 reputation 记忆（供 §17.1/§17.2 未来读取）。"""
        store = MemoryStore(self.db, self.world)
        label = f"因{SCANDAL_TYPE_LABELS.get(s.scandal_type, '争议')}丑闻{'塌房' if collapsed else '争议'}"
        store.write_long(
            "character_agent", f"char:{s.character_id}:notorious",
            value={"label": label, "scandal_id": s.id, "collapsed": collapsed,
                   "opinion": s.public_opinion},
            importance=0.7 if collapsed else 0.5,
        )
        store.write_long(
            "character_agent", f"char:{s.character_id}:reputation",
            value={"public_opinion": s.public_opinion, "stage": s.stage.value,
                   "scandal_id": s.id},
            importance=0.6,
        )
