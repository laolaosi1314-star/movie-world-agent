"""奖项 Agent（Phase 3 规则占位版 + Phase 6 前置：负面奖项 + Phase 3.x：多领域/跨界）。

职责（每个新年份）：
  1. 为各奖项生成当年奖季（season）；
  2. 资格→候选→提名（nominations）→颁奖（winners）；
  3. 叙事统计（award_season_stats）：最大赢家/遗珠/最年轻/最年长；
  4. 成就累计（award_achievements）：自动生成"X提Y中"；
  5. 负面奖项（金酸梅式）：基于低分与烂口碑选出"最差"，颁奖事件类别为"负面奖项"，
     并把结果写入世界记忆 sharp_topics 作为后续"尖锐话题"（媒体 Agent 生成争议通稿）；
  6. 【Phase 3.x 新增】多领域/跨界：领域(domain)×正副(award_type)×类目客体(kind)
     三正交轴。电影/电视/音乐共用同一引擎，按各类别自身 domain 取候选与评分；
     负奖跨领域同样走 sharp_topics→争议通稿闭环（domain 无关）。

性别细分：若人物 attributes.gender 为 male/female 则区分男女演员/歌手奖；否则回退到
"最佳主演"。这是规则占位，留作【返工点】（建议 Character 增加正式 gender 列）。
"""
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.award import (
    Award, AwardSeason, AwardCategory, Nomination, Winner,
    AwardSeasonStat, AwardAchievement,
)
from app.models.project import Project, ProjectCast, ProjectType
from app.models.market import ProjectMarket
from app.models.character import Character, CharacterType
from app.models.event import Event
from app.models.enums import (
    EventLevel, AwardNarrativeTag, AwardType, WorkDomain, CategoryKind,
)
from app.sim.memory import MemoryStore

# ---------------------------------------------------------------------------
# 领域映射：Project.type -> WorkDomain（Agent 内常量，§15.2）
# ---------------------------------------------------------------------------
PROJECT_TYPE_TO_DOMAIN = {
    ProjectType.FILM: WorkDomain.FILM,
    ProjectType.TV: WorkDomain.TV,
    ProjectType.WEBSERIES: WorkDomain.TV,
    ProjectType.VARIETY: WorkDomain.TV,
    ProjectType.ANIMATION: WorkDomain.FILM,
    ProjectType.DOCUMENTARY: WorkDomain.FILM,
    ProjectType.SHORT: WorkDomain.FILM,
    ProjectType.ALBUM: WorkDomain.MUSIC,
    ProjectType.SINGLE: WorkDomain.MUSIC,
}

# 每个领域下，可被"作品类"类别纳入的作品类型集合
DOMAIN_PROJECT_TYPES = {
    WorkDomain.FILM: {ProjectType.FILM, ProjectType.ANIMATION,
                      ProjectType.DOCUMENTARY, ProjectType.SHORT},
    WorkDomain.TV: {ProjectType.TV, ProjectType.WEBSERIES, ProjectType.VARIETY},
    WorkDomain.MUSIC: {ProjectType.ALBUM, ProjectType.SINGLE},
}


def _def(name, kind):
    return {"name": name, "kind": kind}


# 分领域、分正/负的类目定义（驱动表，替代旧两套硬编码列表）
FILM_POSITIVE = [
    _def("最佳影片", CategoryKind.PROJECT),
    _def("最佳导演", CategoryKind.DIRECTOR),
    _def("最佳男演员", CategoryKind.ACTOR_MALE),
    _def("最佳女演员", CategoryKind.ACTOR_FEMALE),
    _def("最佳编剧", CategoryKind.WRITER),
]
FILM_NEGATIVE = [
    _def("最差影片", CategoryKind.PROJECT),
    _def("最差导演", CategoryKind.DIRECTOR),
    _def("最差男演员", CategoryKind.ACTOR_MALE),
    _def("最差女演员", CategoryKind.ACTOR_FEMALE),
    _def("最差编剧", CategoryKind.WRITER),
]
TV_POSITIVE = [
    _def("最佳剧集", CategoryKind.PROJECT),
    _def("最佳导演(剧集)", CategoryKind.DIRECTOR),
    _def("最佳男主角", CategoryKind.ACTOR_MALE),
    _def("最佳女主角", CategoryKind.ACTOR_FEMALE),
    _def("最佳编剧(剧集)", CategoryKind.WRITER),
]
TV_NEGATIVE = [
    _def("最差剧集", CategoryKind.PROJECT),
    _def("最差导演(剧集)", CategoryKind.DIRECTOR),
    _def("最差男主角", CategoryKind.ACTOR_MALE),
    _def("最差女主角", CategoryKind.ACTOR_FEMALE),
    _def("最差编剧(剧集)", CategoryKind.WRITER),
]
MUSIC_POSITIVE = [
    _def("最佳专辑", CategoryKind.ALBUM),
    _def("最佳单曲", CategoryKind.SINGLE),
    _def("最佳男歌手", CategoryKind.SINGER_MALE),
    _def("最佳女歌手", CategoryKind.SINGER_FEMALE),
    _def("最佳作词", CategoryKind.LYRICIST),
    _def("最佳作曲", CategoryKind.COMPOSER),
]
MUSIC_NEGATIVE = [
    _def("最差专辑", CategoryKind.ALBUM),
    _def("最差单曲", CategoryKind.SINGLE),
    _def("最差男歌手", CategoryKind.SINGER_MALE),
    _def("最差女歌手", CategoryKind.SINGER_FEMALE),
    _def("最差作词", CategoryKind.LYRICIST),
    _def("最差作曲", CategoryKind.COMPOSER),
]

CATEGORY_DEFS = {
    (WorkDomain.FILM, AwardType.POSITIVE): FILM_POSITIVE,
    (WorkDomain.FILM, AwardType.NEGATIVE): FILM_NEGATIVE,
    (WorkDomain.TV, AwardType.POSITIVE): TV_POSITIVE,
    (WorkDomain.TV, AwardType.NEGATIVE): TV_NEGATIVE,
    (WorkDomain.MUSIC, AwardType.POSITIVE): MUSIC_POSITIVE,
    (WorkDomain.MUSIC, AwardType.NEGATIVE): MUSIC_NEGATIVE,
}

# 名称 -> kind 快速查表（供种子按名填 kind）
CATEGORY_KIND_LOOKUP = {}
for (_d, _t), _defs in CATEGORY_DEFS.items():
    for _c in _defs:
        CATEGORY_KIND_LOOKUP[(_d, _t, _c["name"])] = _c["kind"]


# 兼容旧单测 / 旧调用方：电影正/负类目别名（内容不变）
POSITIVE_CATEGORY_DEFS = FILM_POSITIVE
NEGATIVE_CATEGORY_DEFS = FILM_NEGATIVE


# 新世界首次无奖项时播种的默认奖项（正+负，覆盖三大领域），保证体系开箱可用
DEFAULT_AWARDS = [
    {"name": "金屏奖", "domain": WorkDomain.FILM, "award_type": AwardType.POSITIVE,
     "categories": [c["name"] for c in FILM_POSITIVE]},
    {"name": "金酸梅奖", "domain": WorkDomain.FILM, "award_type": AwardType.NEGATIVE,
     "categories": [c["name"] for c in FILM_NEGATIVE]},
    {"name": "金屏剧奖", "domain": WorkDomain.TV, "award_type": AwardType.POSITIVE,
     "categories": [c["name"] for c in TV_POSITIVE]},
    {"name": "金唱片奖", "domain": WorkDomain.MUSIC, "award_type": AwardType.POSITIVE,
     "categories": [c["name"] for c in MUSIC_POSITIVE]},
    {"name": "金酸梅剧奖", "domain": WorkDomain.TV, "award_type": AwardType.NEGATIVE,
     "categories": [c["name"] for c in TV_NEGATIVE]},
    {"name": "金扫帚奖", "domain": WorkDomain.MUSIC, "award_type": AwardType.NEGATIVE,
     "categories": [c["name"] for c in MUSIC_NEGATIVE]},
]


class WorkEvaluator:
    """按领域抽取作品评分指标（确定性、可重放）。

    三领域通用 quality / audience_score / media_score；电视收视率、音乐
    销量/流媒体/榜单存于 extra，供未来 sim 指针使用，**不影响**当前 _badness
    判定（仍用通用口碑分项，保持跨领域一致的"越烂越突出"语义）。
    """

    def __init__(self, domain: WorkDomain):
        self.domain = domain

    def evaluate(self, project: Project, market: Optional[ProjectMarket]) -> dict:
        quality = None
        if project.composite_quality is not None:
            quality = float(project.composite_quality)
        else:
            qm = project.quality_metrics or {}
            vals = [float(v) for v in qm.values() if isinstance(v, (int, float))]
            quality = sum(vals) / len(vals) if vals else 50.0

        audience = media = trajectory = None
        extra = {}
        if market is not None:
            audience = float(market.audience_score) if market.audience_score is not None else None
            media = float(market.media_score) if market.media_score is not None else None
            trajectory = market.word_of_mouth_trajectory
            if self.domain == WorkDomain.TV and market.rating is not None:
                extra["rating"] = float(market.rating)
            if self.domain == WorkDomain.MUSIC:
                for k in ("sales", "streams", "chart_position"):
                    v = getattr(market, k, None)
                    if v is not None:
                        extra[k] = float(v)
        return {"quality": quality, "audience_score": audience,
                "media_score": media, "trajectory": trajectory, "extra": extra}


class AwardAgent:
    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick

    def _quality(self, project: Project):
        if project.composite_quality is not None:
            return float(project.composite_quality)
        qm = project.quality_metrics or {}
        vals = [float(v) for v in qm.values() if isinstance(v, (int, float))]
        return sum(vals) / len(vals) if vals else 50.0

    def _reputation_penalty(self, person) -> float:
        """§17.3 桥接：从重案人物的活跃实锤丑闻计算「劣迹加成」，喂入负奖 _badness。"""
        try:
            from app.sim import crisis_agent
            return crisis_agent.scandal_reputation_penalty(self.db, self.world, person.id)
        except Exception:
            return 0.0

    def _badness(self, entry: dict) -> float:
        """负面判定算法（跨领域通用）：低分 + 烂口碑 -> 越大越"烂"。

        组成（确定性、可重放）：
          - 质量分越低越烂： (100 - quality) × 0.5
          - 观众评分越低越烂：(100 - audience_score) × 0.3
          - 媒体评分越低越烂：(100 - media_score) × 0.2
          - 口碑轨迹"高开低走"额外惩罚 +10
        全部来自数据库既有事实，不引入随机；电视/音乐负奖直接复用。
        """
        quality = entry.get("quality")
        mkt = entry.get("market") or {}
        aud = mkt.get("audience_score")
        med = mkt.get("media_score")
        traj = mkt.get("trajectory")
        bad = 0.0
        if quality is not None:
            bad += (100.0 - float(quality)) * 0.5
        if aud is not None:
            bad += (100.0 - float(aud)) * 0.3
        if med is not None:
            bad += (100.0 - float(med)) * 0.2
        if traj == "high_open_low_close":
            bad += 10.0
        return bad

    def _crew(self, project: Project) -> dict:
        """取该作品剧组人物，按类型归类（含音乐人/作曲）。"""
        cast_rows = self.db.query(ProjectCast).filter(ProjectCast.project_id == project.id).all()
        chars = (
            self.db.query(Character).filter(Character.id.in_([r.character_id for r in cast_rows])).all()
            if cast_rows else []
        )
        mapping = {ch.id: ch for ch in chars}

        def of_type(t):
            return [mapping[r.character_id] for r in cast_rows
                    if mapping.get(r.character_id) and mapping[r.character_id].type == t]

        directors = of_type(CharacterType.DIRECTOR)
        actors = of_type(CharacterType.ACTOR)
        writers = of_type(CharacterType.WRITER)
        singers = of_type(CharacterType.SINGER)
        composers = of_type(CharacterType.COMPOSER)
        return {
            "director": directors[0] if directors else None,
            "writer": writers[0] if writers else None,
            "composer": composers[0] if composers else None,
            "actors": actors,
            "singers": singers,
        }

    def _first_by_gender(self, chars, gender):
        for c in chars:
            if (c.attributes or {}).get("gender") == gender:
                return c
        return None

    def _eligible_works(self, domain: WorkDomain):
        """取该领域下已上映作品，并批量附最新市场表现（避免 N+1）。"""
        projects = (
            self.db.query(Project)
            .filter(Project.world_id == self.world.id, Project.status == "released")
            .all()
        )
        eligible = [p for p in projects
                    if PROJECT_TYPE_TO_DOMAIN.get(p.type) == domain]
        pm_rows = (
            self.db.query(ProjectMarket)
            .filter(ProjectMarket.project_id.in_([p.id for p in eligible]))
            .all()
        ) if eligible else []
        latest = {}
        for pm in pm_rows:
            if pm.project_id not in latest or pm.id > latest[pm.project_id].id:
                latest[pm.project_id] = pm

        evaluator = WorkEvaluator(domain)
        enriched = []
        for p in eligible:
            crew = self._crew(p)
            pm = latest.get(p.id)
            ev = evaluator.evaluate(p, pm)
            enriched.append({
                "project": p, "quality": ev["quality"],
                "director": crew["director"], "actors": crew["actors"],
                "writer": crew["writer"], "singers": crew["singers"],
                "composer": crew["composer"],
                "market": {
                    "audience_score": ev["audience_score"],
                    "media_score": ev["media_score"],
                    "trajectory": ev["trajectory"],
                },
            })
        return enriched

    def _pick(self, kind: CategoryKind, entry: dict):
        """按类别客体种类取该作品的候选人物（或无，作品类返回 None）。"""
        if kind in (CategoryKind.PROJECT, CategoryKind.ALBUM, CategoryKind.SINGLE):
            return None  # 候选即作品本身
        if kind == CategoryKind.DIRECTOR:
            return entry["director"]
        if kind == CategoryKind.WRITER:
            return entry["writer"]
        if kind == CategoryKind.COMPOSER:
            return entry["composer"]
        if kind == CategoryKind.LYRICIST:
            return entry["writer"]  # WRITER 映射作词
        if kind in (CategoryKind.ACTOR_MALE, CategoryKind.ACTOR_FEMALE):
            gender = "male" if kind == CategoryKind.ACTOR_MALE else "female"
            return self._first_by_gender(entry["actors"], gender)
        if kind in (CategoryKind.SINGER_MALE, CategoryKind.SINGER_FEMALE):
            gender = "male" if kind == CategoryKind.SINGER_MALE else "female"
            return self._first_by_gender(entry["singers"], gender)
        return None

    def _seed_default_awards(self):
        """新世界若没有任何奖项，则播种三大领域正/负默认奖项，保证体系开箱可用。"""
        exists = self.db.query(Award).filter(Award.world_id == self.world.id).first()
        if exists:
            return
        for spec in DEFAULT_AWARDS:
            award = Award(
                world_id=self.world.id, name=spec["name"],
                founded_year=self.world.current_year,
                organizer="组委会",
                positioning=("年度表彰" if spec["award_type"] == AwardType.POSITIVE
                             else "年度吐槽"),
                award_type=spec["award_type"],
                domain=spec["domain"],
            )
            self.db.add(award)
            self.db.flush()
            for cat_name in spec["categories"]:
                kind = CATEGORY_KIND_LOOKUP[(spec["domain"], spec["award_type"], cat_name)]
                self.db.add(AwardCategory(
                    award_id=award.id, name=cat_name,
                    award_type=spec["award_type"],
                    domain=spec["domain"], kind=kind))
        self.db.flush()

    def _ensure_seasons(self):
        self._seed_default_awards()
        awards = self.db.query(Award).filter(Award.world_id == self.world.id).all()
        pending = {}
        for award in awards:
            last = (
                self.db.query(AwardSeason)
                .filter(AwardSeason.award_id == award.id)
                .order_by(AwardSeason.year.desc()).first()
            )
            if last and last.year >= self.world.current_year:
                continue
            season_number = (last.season_number + 1) if last else 1
            season = AwardSeason(
                award_id=award.id, season_number=season_number,
                year=self.world.current_year, status="ceremony",
            )
            self.db.add(season)
            self.db.flush()
            pending[award.id] = season
        return pending

    def _run_season(self, award: Award, season: AwardSeason, entries):
        is_negative = award.award_type == AwardType.NEGATIVE
        cat_defs = CATEGORY_DEFS[(award.domain, award.award_type)]

        # 累计：每类别候选 (person/project -> 评分)；正奖取 quality，负奖取 badness
        cat_candidates = defaultdict(list)
        for cat in cat_defs:
            kind = cat["kind"]
            for e in entries:
                ptype = e["project"].type
                if kind == CategoryKind.PROJECT:
                    if ptype not in DOMAIN_PROJECT_TYPES[award.domain]:
                        continue
                    person = None
                elif kind == CategoryKind.ALBUM:
                    if ptype != ProjectType.ALBUM:
                        continue
                    person = None
                elif kind == CategoryKind.SINGLE:
                    if ptype != ProjectType.SINGLE:
                        continue
                    person = None
                else:
                    person = self._pick(kind, e)
                    if person is None:
                        continue  # 无对应客体（如缺该性别演员）则不产生候选
                score = self._badness(e) if is_negative else e["quality"]
                # §17.3 桥接：丑闻缠身者（已曝光+实锤）在负奖中更易被点名
                if is_negative and person is not None:
                    score = score + self._reputation_penalty(person)
                cat_candidates[cat["name"]].append((e, person, score))

        season_winners = []  # (target_type, target_id, label)
        for cat in cat_defs:
            cands = cat_candidates.get(cat["name"], [])
            if not cands:
                continue
            # 两者皆取 score 最大者：正奖 quality 高=优，负奖 badness 高=烂
            cands_sorted = sorted(cands, key=lambda x: x[2], reverse=True)[:5]
            winner_entry, winner_person, _ = cands_sorted[0]
            is_project_target = cat["kind"] in (
                CategoryKind.PROJECT, CategoryKind.ALBUM, CategoryKind.SINGLE)
            for (e, person, _) in cands_sorted:
                project_id = e["project"].id if is_project_target else None
                character_id = person.id if person else None
                self.db.add(Nomination(
                    season_id=season.id,
                    category_id=0,  # 预定义类别未落 award_categories，留作返工点
                    category_name=cat["name"],
                    project_id=project_id, character_id=character_id,
                ))
            w_project = winner_entry["project"].id if is_project_target else None
            w_char = winner_person.id if winner_person else None
            self.db.add(Winner(
                season_id=season.id, category_id=0,
                category_name=cat["name"],
                project_id=w_project, character_id=w_char,
            ))
            if w_char:
                season_winners.append(("character", w_char, f"{cat['name']}→{winner_person.name}"))
            elif w_project:
                season_winners.append(("project", w_project, f"{cat['name']}→《{winner_entry['project'].title}》"))

        self._stats_and_achievements(award, season, season_winners)

        # 事件：正奖"奖项"（媒体转奖项预测），负奖"负面奖项→争议"
        event_category = "负面奖项" if is_negative else "奖项"
        event_level = EventLevel.MAJOR
        self.db.add(Event(
            world_id=self.world.id, tick_id=self.tick.id,
            event_date=self.tick.to_date.date(), level=event_level,
            category=event_category,
            title=f"{award.name} 第{season.season_number}届颁奖",
            description="；".join(label for _, _, label in season_winners) or "本届无主要奖项",
            causal_chain={"season": season.season_number, "award_type": award.award_type.value,
                          "domain": award.domain.value},
            affected_entities=[{"type": "award", "id": award.id}],
        ))

        # 负面奖项 -> 写入世界记忆 sharp_topics，供媒体 Agent 后续生成争议通稿
        # （domain 无关：电视/音乐负奖自动进入该闭环，媒体 Agent 无需改动）
        if is_negative:
            self._record_sharp_topics(award, season, season_winners)

    def _record_sharp_topics(self, award, season, season_winners):
        store = MemoryStore(self.db, self.world)
        mem = store.recall_one("world", MemoryScope.WORLD, "sharp_topics")
        topics = mem.value if mem and isinstance(mem.value, list) else []
        for _ttype, _tid, label in season_winners:
            topics.append({
                "headline": f"{award.name}第{season.season_number}届：{label}",
                "award_name": award.name,
                "domain": award.domain.value,
                "season": season.season_number,
                "target_label": label,
                "created_tick": self.tick.tick_index,
                "consumed": False,
            })
        store.write_world("sharp_topics", topics, importance=0.95)

    def _stats_and_achievements(self, award, season, season_winners):
        store = MemoryStore(self.db, self.world)
        is_negative = award.award_type == AwardType.NEGATIVE
        for ttype, tid, label in season_winners:
            if ttype == "character":
                if is_negative:
                    # 负奖：写入"劣迹/翻车"记忆（供媒体背景注脚），不当"荣誉"
                    store.write_long(
                        agent="character_agent", key=f"char:{tid}:notorious",
                        value={"label": label, "season": season.season_number,
                               "year": self.world.current_year},
                        importance=0.6)
                else:
                    store.write_long(
                        agent="character_agent", key=f"char:{tid}:honor",
                        value={"label": label, "season": season.season_number,
                               "year": self.world.current_year},
                        importance=0.7)

        # 最大赢家 / 最年轻 / 最年长：仅正奖有意义
        if not is_negative:
            tally = defaultdict(int)
            for ttype, tid, _ in season_winners:
                tally[(ttype, tid)] += 1
            if tally:
                (top_type, top_id), top_n = max(tally.items(), key=lambda kv: kv[1])
                if top_n >= 2:
                    self.db.add(AwardSeasonStat(
                        season_id=season.id, tag=AwardNarrativeTag.BIGGEST_WINNER,
                        target_type=top_type, target_id=top_id,
                        description=f"斩获 {top_n} 项大奖，为本届最大赢家。",
                    ))

            char_wins = [(tid, self.db.get(Character, tid)) for (tt, tid) in season_winners if tt == "character"]
            chars_with_year = [(c.birth_year, tid) for tid, c in char_wins if c and c.birth_year]
            if chars_with_year:
                y_min, id_min = min(chars_with_year)
                y_max, id_max = max(chars_with_year)
                self.db.add(AwardSeasonStat(
                    season_id=season.id, tag=AwardNarrativeTag.YOUNGEST_WINNER,
                    target_type="character", target_id=id_min,
                    description=f"出生年份 {y_min}，本届最年轻获奖者。",
                ))
                self.db.add(AwardSeasonStat(
                    season_id=season.id, tag=AwardNarrativeTag.OLDEST_WINNER,
                    target_type="character", target_id=id_max,
                    description=f"出生年份 {y_max}，本届最年长获奖者。",
                ))

        # 成就累计（提名/获奖）：正负奖都累计，便于"X提Y中"回顾
        nom_chars = set()
        win_chars = set()
        for (ttype, tid, _) in season_winners:
            if ttype == "character":
                win_chars.add(tid)
        noms = self.db.query(Nomination).filter(Nomination.season_id == season.id,
                                                Nomination.character_id.isnot(None)).all()
        for n in noms:
            nom_chars.add(n.character_id)
        for cid in nom_chars | win_chars:
            ach = (
                self.db.query(AwardAchievement)
                .filter(AwardAchievement.award_id == award.id, AwardAchievement.character_id == cid)
                .first()
            )
            if not ach:
                ach = AwardAchievement(award_id=award.id, character_id=cid,
                                       nominations_count=0, wins_count=0)
                self.db.add(ach)
                self.db.flush()
            ach.nominations_count = (ach.nominations_count or 0) + (1 if cid in nom_chars else 0)
            ach.wins_count = (ach.wins_count or 0) + (1 if cid in win_chars else 0)
            n, w = ach.nominations_count, ach.wins_count
            ach.note = f"{n}提{w}中" if n else None

    def run(self):
        pending = self._ensure_seasons()
        # 按领域预取候选（每领域一次批量查询），各奖项只用自己 domain 的候选
        by_domain = {
            WorkDomain.FILM: self._eligible_works(WorkDomain.FILM),
            WorkDomain.TV: self._eligible_works(WorkDomain.TV),
            WorkDomain.MUSIC: self._eligible_works(WorkDomain.MUSIC),
        }
        for award_id, season in pending.items():
            award = self.db.get(Award, award_id)
            entries = by_domain.get(award.domain, [])
            self._run_season(award, season, entries)
        self.db.flush()
