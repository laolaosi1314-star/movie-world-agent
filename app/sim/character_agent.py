"""人物 Agent（Phase 1 规则占位版 + Phase 5 记忆增强）。

职责：在每次 tick 中驱动人物状态演化。
设计约束：禁止纯随机；属性变更必须基于规则，并记录到 character_attribute_log 留痕。

Phase 5 记忆增强：
  - 决策读取"世界记忆"（行业气候）与"自身长期记忆"（人气动量 / 奖项荣誉）作为
    确定性偏置——记忆只调方向/幅度，结果仍被钳制在 [0,100] 并留痕，绝不替代因果。
  - 每个 tick 写入"短期草稿"（本 tick 人气快照，按时效清理）；
  - 沉淀"长期记忆：人气动量"（跨 tick 自我强化趋势，经巩固长期保留）。
"""
from sqlalchemy.orm import Session
from app.models.character import (
    Character, CharacterAttributeLog, CharacterCareerHistory,
)
from app.models.world import World, SimulationTick
from app.models.enums import CharacterStatus, MemoryScope
from app.sim.memory import MemoryStore


class CharacterAgent:
    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick
        self.store = MemoryStore(db, world)

    def _bounded_delta(self, character: Character) -> int:
        """确定性、有界（±1）的扰动，绝不主导结果。"""
        return ((character.id + self.tick.tick_index) % 3) - 1

    def run(self):
        # 读取世界记忆：行业气候偏置（全 Agent 共享）
        climate = self.store.recall_one(
            agent="world", scope=MemoryScope.WORLD, key="industry_climate")
        climate_bias = 0
        if climate and isinstance(climate.value, dict):
            climate_bias = int(climate.value.get("heat_trend", 0) or 0)

        chars = (
            self.db.query(Character)
            .filter(Character.world_id == self.world.id,
                    Character.status == CharacterStatus.ACTIVE)
            .all()
        )
        movements = []
        for c in chars:
            attrs = dict(c.attributes or {})
            base_heat = int(attrs.get("heat", 50) or 50)

            # 记忆偏置 1：自身长期"人气动量"（上一 tick 沉淀，经巩固长期保留）
            momentum = self.store.recall_one(
                agent="character_agent", scope=MemoryScope.LONG,
                key=f"char:{c.id}:momentum")
            momentum_bias = 0
            if momentum and isinstance(momentum.value, dict):
                d = momentum.value.get("delta") or 0
                momentum_bias = 1 if d > 0 else (-1 if d < 0 else 0)

            # 记忆偏置 2：奖项荣誉（由 AwardAgent 写入的长期记忆，长尾人气）
            honor = self.store.recall_one(
                agent="character_agent", scope=MemoryScope.LONG,
                key=f"char:{c.id}:honor")
            honor_bonus = 1 if honor else 0

            delta = self._bounded_delta(c) + climate_bias + momentum_bias + honor_bonus
            new_heat = max(0, min(100, base_heat + delta))
            movements.append(delta)
            if new_heat != base_heat:
                attrs["heat"] = new_heat
                reasons = ["tick 规则演化（有界扰动）"]
                if momentum_bias:
                    reasons.append(f"人气动量记忆（上一期{'上升' if momentum_bias > 0 else '下降'}）")
                if honor_bonus:
                    reasons.append("奖项荣誉记忆（往届获奖带来的长尾人气）")
                if climate_bias:
                    reasons.append(f"行业气候记忆（{'回暖' if climate_bias > 0 else '降温'}）")
                self.db.add(CharacterAttributeLog(
                    character_id=c.id, tick_id=self.tick.id, field="heat",
                    old_value={"heat": base_heat},
                    new_value={"heat": new_heat},
                    reason="；".join(reasons),
                ))
                c.attributes = attrs
                # 短期草稿：本 tick 的人气快照（重要度低于巩固阈值，ttl 到点即清理，不沉淀为长期）
                self.store.write_short(
                    agent="character_agent", key=f"char:{c.id}:tick_heat",
                    value={"heat": new_heat, "year": self.world.current_year,
                           "month": self.world.current_month}, ttl_ticks=3,
                    importance=0.15)
                # 长期记忆：沉淀"人气动量"，跨 tick 自我强化趋势
                self.store.write_long(
                    agent="character_agent", key=f"char:{c.id}:momentum",
                    value={"heat": new_heat, "delta": new_heat - base_heat},
                    importance=0.5)

            # 每 12 个 tick（约一年）追加一条生涯里程碑
            if self.tick.tick_index % 12 == 0:
                self.db.add(CharacterCareerHistory(
                    character_id=c.id,
                    year=self.world.current_year,
                    month=self.world.current_month,
                    title=f"{c.name} 持续活跃于影视行业",
                    description="系统按年度自动记录的生涯节点（占位）。",
                ))

        # 世界记忆：本 tick 行业整体人气走向（供下一 tick 与其它 Agent 读取）
        if movements:
            avg = sum(movements) / len(movements)
            trend = 1 if avg > 0.2 else (-1 if avg < -0.2 else 0)
            self.store.write_world(
                key="industry_climate",
                value={"heat_trend": trend, "avg_movement": round(avg, 3),
                       "updated_tick": self.world.total_ticks})
        self.db.flush()
