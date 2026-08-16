"""电影节 Agent（Phase 3 规则占位版）。

职责（每个新年份）：
  1. 为各电影节生成当年届次（edition）；
  2. 选拔：从已上映作品中按质量入围各单元；
  3. 颁奖：为各单元产出奖项（最佳影片/导演/主演/编剧）。

说明：类别未区分男女演员（Character 无 gender 字段，留作【返工点】），规则占位用
"最佳影片/导演/主演/编剧"四类，可由上帝模式或后续扩展细化。
"""
from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.festival import (
    Festival, FestivalEdition, FestivalSelection, FestivalAward,
)
from app.models.project import Project, ProjectCast
from app.models.character import Character
from app.models.event import Event
from app.models.enums import EventLevel, FestivalSection, CharacterType, ProjectType

FESTIVAL_AWARD_CATEGORIES = ["最佳影片", "最佳导演", "最佳主演", "最佳编剧"]


class FestivalAgent:
    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick

    def _released_projects(self):
        return (
            self.db.query(Project)
            .filter(Project.world_id == self.world.id, Project.status == "released")
            .order_by(Project.composite_quality.desc().nullslast(), Project.id)
            .all()
        )

    def _crew(self, project: Project):
        cast_rows = self.db.query(ProjectCast).filter(ProjectCast.project_id == project.id).all()
        chars = (
            self.db.query(Character).filter(Character.id.in_([r.character_id for r in cast_rows])).all()
            if cast_rows else []
        )
        mapping = {ch.id: ch for ch in chars}
        director = next((mapping[r.character_id] for r in cast_rows
                         if mapping.get(r.character_id) and mapping[r.character_id].type == CharacterType.DIRECTOR), None)
        actors = [mapping[r.character_id] for r in cast_rows
                  if mapping.get(r.character_id) and mapping[r.character_id].type == CharacterType.ACTOR]
        writer = next((mapping[r.character_id] for r in cast_rows
                       if mapping.get(r.character_id) and mapping[r.character_id].type == CharacterType.WRITER), None)
        return director, actors, writer

    def _ensure_editions(self):
        """返回 (festival_id -> edition) 仅含本年新创建/待处理的届次。"""
        festivals = self.db.query(Festival).filter(Festival.world_id == self.world.id).all()
        result = {}
        for f in festivals:
            last = (
                self.db.query(FestivalEdition)
                .filter(FestivalEdition.festival_id == f.id)
                .order_by(FestivalEdition.year.desc()).first()
            )
            if last and last.year >= self.world.current_year:
                continue  # 本年已处理
            edition_number = (last.edition_number + 1) if last else 1
            edition = FestivalEdition(
                festival_id=f.id, edition_number=edition_number,
                year=self.world.current_year, status="ongoing",
            )
            self.db.add(edition)
            self.db.flush()
            result[f.id] = edition
        return result

    def _select_and_award(self, festival: Festival, edition: FestivalEdition, projects):
        if not projects:
            return
        top = projects[:5]
        # 主竞赛选拔
        for p in top:
            self.db.add(FestivalSelection(
                edition_id=edition.id, section=FestivalSection.MAIN_COMPETITION,
                project_id=p.id, selection_type="selected",
            ))
        # 其他单元按类型过滤
        for p in projects:
            if p.type == ProjectType.DOCUMENTARY:
                self.db.add(FestivalSelection(
                    edition_id=edition.id, section=FestivalSection.DOCUMENTARY,
                    project_id=p.id, selection_type="selected"))
            elif p.type == ProjectType.SHORT:
                self.db.add(FestivalSelection(
                    edition_id=edition.id, section=FestivalSection.SHORT,
                    project_id=p.id, selection_type="selected"))

        # 颁奖：从主竞赛入围作品取各品类赢家
        for category in FESTIVAL_AWARD_CATEGORIES:
            winner_project = top[0]
            director, actors, writer = self._crew(winner_project)
            winner_character = None
            if category == "最佳导演":
                winner_character = director
            elif category == "最佳主演":
                winner_character = actors[0] if actors else None
            elif category == "最佳编剧":
                winner_character = writer
            # 最佳影片不挂人物
            self.db.add(FestivalAward(
                edition_id=edition.id, category=category,
                winner_project_id=winner_project.id if category == "最佳影片" else None,
                winner_character_id=winner_character.id if winner_character else None,
            ))
        edition.status = "completed"
        self.db.add(Event(
            world_id=self.world.id, tick_id=self.tick.id,
            event_date=self.tick.to_date.date(), level=EventLevel.IMPORTANT,
            category="电影节",
            title=f"{festival.name} 第{edition.edition_number}届落幕",
            description=f"最佳影片：《{top[0].title}》",
            causal_chain={"edition": edition.edition_number, "top_film": top[0].title},
            affected_entities=[{"type": "festival", "id": festival.id}],
        ))

    def run(self):
        pending = self._ensure_editions()
        projects = self._released_projects()
        for festival_id, edition in pending.items():
            festival = self.db.get(Festival, festival_id)
            self._select_and_award(festival, edition, projects)
        self.db.flush()
