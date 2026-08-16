"""市场 / 票房 Agent（Phase 2 规则占位版）。

核心：票房**禁止随机**。由多因子因果模型计算：
  base = 加权(演员商业价值, 导演商业价值, IP热度, 类型基准, 制作规模, 宣发, 竞争, 市场热度)
  box_office = base × 口碑系数 × (1 + 有界噪声)
结果分类（outcome）可追溯，噪声仅 ±8% 且记入 factors。
"""
from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.market import MarketSnapshot, ProjectMarket
from app.models.project import Project, ProjectCast
from app.models.character import Character
from app.models.event import Event
from app.models.enums import (
    EventLevel, MarketOutcome, CharacterType, ProjectType,
)
from app.sim.util import bounded_noise, clamp, weighted_avg

# 类型基准票房权重（相对）
TYPE_BASELINE = {
    ProjectType.FILM: 60.0,
    ProjectType.TV: 40.0,
    ProjectType.WEBSERIES: 35.0,
    ProjectType.VARIETY: 30.0,
    ProjectType.ANIMATION: 55.0,
    ProjectType.DOCUMENTARY: 25.0,
    ProjectType.SHORT: 10.0,
}

# 档期系数（按 release_month）
SLOT_FACTOR = {
    1: 0.9, 2: 0.8, 3: 1.0, 4: 0.95, 5: 1.05, 6: 1.1,
    7: 1.2, 8: 1.15, 9: 1.0, 10: 1.05, 11: 1.1, 12: 1.3,
}


class MarketAgent:
    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick

    def _snapshot_environment(self):
        """整体市场快照：环境 + 热度（确定性，由 world 状态驱动）。"""
        # 热度随行业状态在确定性基线附近波动
        base_heat = {"繁荣": 80.0, "平稳": 55.0, "低迷": 35.0}.get(self.world.industry_status, 55.0)
        noise = bounded_noise(self.world.id, self.tick.tick_index, self.world.rng_seed, amplitude=0.05)
        heat = clamp(base_heat * (1 + noise), 0, 100)
        env = self.world.industry_status
        self.db.add(MarketSnapshot(
            world_id=self.world.id, tick_id=self.tick.id,
            snapshot_date=self.tick.to_date, environment=env, heat=heat,
            notes="tick 市场快照（规则占位）。",
        ))
        return heat

    def _crew_values(self, project: Project):
        """取主演/导演的商业价值均值（attributes 缺省时回落到 heat/默认）。"""
        cast_rows = (
            self.db.query(ProjectCast)
            .filter(ProjectCast.project_id == project.id)
            .all()
        )
        char_ids = [r.character_id for r in cast_rows]
        chars = self.db.query(Character).filter(Character.id.in_(char_ids)).all() if char_ids else []
        actors, directors = [], []
        for ch in chars:
            attrs = ch.attributes or {}
            val = float(attrs.get("commercial_value", attrs.get("heat", 50)))
            if ch.type == CharacterType.ACTOR:
                actors.append(val)
            elif ch.type == CharacterType.DIRECTOR:
                directors.append(val)
        actor_value = sum(actors) / len(actors) if actors else 50.0
        director_value = sum(directors) / len(directors) if directors else 50.0
        return actor_value, director_value

    def _compute_box_office(self, project: Project, market_heat: float):
        qm = project.quality_metrics or {}
        actor_value, director_value = self._crew_values(project)
        ip_heat = float(qm.get("ip_heat", 40))
        type_baseline = TYPE_BASELINE.get(project.type, 50.0)
        prod_scale = float(qm.get("production_scale", 50))
        promo = float(qm.get("promotion_budget", 50))
        slot = SLOT_FACTOR.get(project.release_month or 6, 1.0)
        # 竞争：同年上映作品越多，单部摊薄
        same_year = (
            self.db.query(Project)
            .filter(Project.world_id == self.world.id, Project.release_year == project.release_year,
                    Project.status == "released")
            .count()
        )
        competition = clamp(100 - same_year * 8, 20, 100)

        # 加权综合（因果因子，全部可追溯）
        base_quality = weighted_avg([
            (actor_value, 0.25), (director_value, 0.20), (ip_heat, 0.10),
            (type_baseline, 0.10), (prod_scale, 0.15), (promo, 0.10), (competition, 0.10),
        ])
        # 映射为亿元：base_quality 0..100 → 0..40 亿；档期修正
        base = base_quality * 0.4 * slot
        # 口碑系数：观众/媒体评分（缺省 7.0）映射到 0.7..1.3
        audience = float(project.audience_score or 7.0)
        media = float(project.media_score or 7.0)
        wom = clamp((audience + media) / 14.0, 0.6, 1.4)
        # 有界噪声
        noise = bounded_noise(project.id, self.tick.tick_index, int(self.world.rng_seed), amplitude=0.08)
        box_office = base * wom * (1 + noise)

        factors = {
            "actor_value": round(actor_value, 2),
            "director_value": round(director_value, 2),
            "ip_heat": ip_heat,
            "type_baseline": type_baseline,
            "production_scale": prod_scale,
            "promotion_budget": promo,
            "competition": round(competition, 2),
            "market_heat": round(market_heat, 2),
            "release_slot": slot,
            "word_of_mouth": round(wom, 3),
            "noise": round(noise, 4),
            "base": round(base, 3),
        }
        return box_office, factors, wom

    def _classify_outcome(self, box_office, factors, wom):
        base = factors["base"]
        if box_office >= base * 1.5 and wom >= 1.1:
            return MarketOutcome.BLOCKBUSTER
        if box_office >= base * 1.3:
            return MarketOutcome.SLEEPER_HIT
        if wom >= 1.15:
            return MarketOutcome.WORD_OF_MOUTH_REVERSAL
        if box_office < base * 0.5:
            return MarketOutcome.HIGH_OPEN_LOW_CLOSE if wom >= 1.0 else MarketOutcome.NORMAL
        return MarketOutcome.NORMAL

    def run(self):
        market_heat = self._snapshot_environment()

        # 扫描已上映但未计算票房的作品
        released = (
            self.db.query(Project)
            .filter(Project.world_id == self.world.id, Project.status == "released")
            .all()
        )
        done_ids = {
            pid for (pid,) in self.db.query(ProjectMarket.project_id)
            .filter(ProjectMarket.world_id == self.world.id).all()
        }
        for p in released:
            if p.id in done_ids:
                continue
            box_office, factors, wom = self._compute_box_office(p, market_heat)
            outcome = self._classify_outcome(box_office, factors, wom)
            p.box_office = round(box_office, 2)
            self.db.add(ProjectMarket(
                world_id=self.world.id, project_id=p.id, tick_id=self.tick.id,
                release_slot=str(p.release_month),
                box_office=round(box_office, 2),
                audience_score=p.audience_score, media_score=p.media_score,
                factors=factors,
                word_of_mouth_trajectory=outcome.value,
                outcome=outcome,
            ))
            self.db.add(Event(
                world_id=self.world.id, tick_id=self.tick.id,
                event_date=self.tick.to_date.date(), level=EventLevel.IMPORTANT,
                category="票房", title=f"《{p.title}》票房出炉：{round(box_office, 2)} 亿",
                description=f"市场形态：{outcome.value}",
                causal_chain=factors,
                affected_entities=[{"type": "project", "id": p.id}],
            ))
        self.db.flush()
