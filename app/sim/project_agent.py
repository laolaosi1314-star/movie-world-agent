"""作品 Agent（Phase 1 规则占位版）。

职责：在每次 tick 中推进作品生命周期状态机。
生命周期：concept → approved → financing → casting → scripting →
          production → postproduction → festival → released。
"""
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.world import World, SimulationTick
from app.models.enums import ProjectStatus
from app.models.event import Event
from app.models.enums import EventLevel

# 生命周期顺序（不含 archived）
LIFECYCLE = [
    ProjectStatus.CONCEPT,
    ProjectStatus.APPROVED,
    ProjectStatus.FINANCING,
    ProjectStatus.CASTING,
    ProjectStatus.SCRIPTING,
    ProjectStatus.PRODUCTION,
    ProjectStatus.POSTPRODUCTION,
    ProjectStatus.FESTIVAL,
    ProjectStatus.RELEASED,
]


class ProjectAgent:
    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick

    def run(self):
        projects = (
            self.db.query(Project)
            .filter(
                Project.world_id == self.world.id,
                Project.status != ProjectStatus.RELEASED,
                Project.status != ProjectStatus.ARCHIVED,
            )
            .all()
        )
        for p in projects:
            try:
                idx = LIFECYCLE.index(p.status)
            except ValueError:
                idx = 0
            if idx < len(LIFECYCLE) - 1:
                nxt = LIFECYCLE[idx + 1]
                p.status = nxt
                if nxt == ProjectStatus.RELEASED:
                    p.release_year = self.world.current_year
                    p.release_month = self.world.current_month
                    self.db.add(Event(
                        world_id=self.world.id,
                        tick_id=self.tick.id,
                        event_date=self.tick.to_date.date(),
                        level=EventLevel.IMPORTANT,
                        category="作品上映",
                        title=f"《{p.title}》上映",
                        description=f"作品《{p.title}》完成生命周期，进入上映阶段。",
                        causal_chain={"phase": "lifecycle", "from": p.status.value},
                        affected_entities=[{"type": "project", "id": p.id}],
                    ))
        self.db.flush()
