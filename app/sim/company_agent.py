"""公司 Agent（Phase 2 规则占位版）。

职责（每次 tick）：
  1. 演化公司资产/能力（确定性有界，非纯随机）；
  2. 不变量：cash < 0 触发破产；
  3. 风格推导：按持续产出的作品类型/质量更新 style_tag；
  4. 追加公司发展历程里程碑。

真实因果逻辑将在 Phase 7 通过 LLMClient 注入；此处用确定性规则演示架构。
"""
from sqlalchemy.orm import Session
from app.models.company import Company, CompanyHistory
from app.models.world import World, SimulationTick
from app.models.project import Project
from app.models.event import Event
from app.models.enums import CompanyStatus, CompanyStyle, EventLevel, ProjectType
from app.sim.util import bounded_noise, clamp

# 作品类型 → 对应风格倾向
TYPE_STYLE = {
    ProjectType.FILM: CompanyStyle.COMMERCIAL_BLOCKBUSTER,
    ProjectType.TV: CompanyStyle.TV_FOCUSED,
    ProjectType.WEBSERIES: CompanyStyle.TV_FOCUSED,
    ProjectType.VARIETY: CompanyStyle.VARIETY,
    ProjectType.DOCUMENTARY: CompanyStyle.ARTHOUSE,
    ProjectType.SHORT: CompanyStyle.ARTHOUSE,
    ProjectType.ANIMATION: CompanyStyle.COMMERCIAL_BLOCKBUSTER,
}


class CompanyAgent:
    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick

    def _evolve(self, c: Company):
        """资产/能力演化：受行业环境确定性影响。"""
        env_factor = 1.0 if self.world.industry_status == "繁荣" else (
            0.4 if self.world.industry_status == "低迷" else 0.7
        )
        noise = bounded_noise(c.id, self.tick.tick_index, self.world.rng_seed)
        delta = int(round((env_factor - 0.6) * 5 + noise * 20))
        c.cash = clamp(c.cash + delta, lo=-10_000_000, hi=None) if False else c.cash + delta
        c.talent_resources = max(0, (c.talent_resources or 0) + (1 if env_factor > 0.8 else 0))
        if c.production_capability is None:
            c.production_capability = 50.0
        c.production_capability = clamp(c.production_capability + noise * 5)

    def _check_bankrupt(self, c: Company):
        if (c.cash or 0) < 0 and c.status == CompanyStatus.ACTIVE:
            c.status = CompanyStatus.BANKRUPT
            self.db.add(CompanyHistory(
                company_id=c.id, year=self.world.current_year, month=self.world.current_month,
                title=f"{c.name} 宣告破产",
                description="资金链断裂，触发破产不变量。",
            ))
            self.db.add(Event(
                world_id=self.world.id, tick_id=self.tick.id,
                event_date=self.tick.to_date.date(), level=EventLevel.MAJOR,
                category="公司", title=f"{c.name} 宣告破产",
                description="资金为负，触发破产不变量。",
                causal_chain={"reason": "cash_negative", "cash": float(c.cash)},
                affected_entities=[{"type": "company", "id": c.id}],
            ))

    def _derive_style(self, c: Company):
        """风格由产出推导：统计该公司已上映作品的类型分布。"""
        projs = (
            self.db.query(Project)
            .filter(Project.company_id == c.id, Project.status == "released")
            .all()
        )
        if not projs:
            return
        from collections import Counter
        style_counter = Counter(TYPE_STYLE.get(p.type, CompanyStyle.COMMERCIAL_BLOCKBUSTER) for p in projs)
        top_style, top_count = style_counter.most_common(1)[0]
        # 仅当占比过半才更新，避免偶发作品改写风格
        if top_count / len(projs) >= 0.5:
            c.style_tag = top_style

    def run(self):
        companies = (
            self.db.query(Company)
            .filter(Company.world_id == self.world.id, Company.status == CompanyStatus.ACTIVE)
            .all()
        )
        for c in companies:
            self._evolve(c)
            self._check_bankrupt(c)
            self._derive_style(c)
            # 每 12 tick（约一年）追加里程碑
            if self.tick.tick_index % 12 == 0:
                self.db.add(CompanyHistory(
                    company_id=c.id, year=self.world.current_year, month=self.world.current_month,
                    title=f"{c.name} 年度经营记录",
                    description=f"行业状态：{self.world.industry_status}；现金：{c.cash}。",
                ))
        self.db.flush()
