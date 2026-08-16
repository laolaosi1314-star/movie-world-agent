"""Phase 4 媒体 Agent：FactPack 构建 -> 文本渲染 -> 新闻落库 + 报告聚合。

架构约束（详见 BLUEPRINT）：
  - LLM 只允许在"表达层"。FactPack 是纯函数从数据库事实聚合而来，
    不含任何随机/模型推断；文本渲染可走模板或 LLM，但无论哪条路径，
    所有数值都必须来自 FactPack，且 LLM 不可参与任何"判定"。
  - LLM 不可用（返回 None / 抛异常）时自动降级到模板，世界演化与新闻落库不受影响。
"""
import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.event import Event
from app.models.enums import (
    EventLevel, NewsType, RenderEngine, MediaOutletType, MediaStance, ReportType,
)
from app.models.media import MediaOutlet
from app.models.news import News
from app.models.project import Project
from app.models.character import Character
from app.models.market import ProjectMarket
from app.sim.memory import MemoryStore
from app.models.enums import MemoryScope
from app.llm.client import get_llm_client


# 新世界首次 tick 时若没有任何媒体机构，则播种这些默认媒体，保证闭环有舆论产出。
DEFAULT_OUTLETS = [
    {"name": "影艺日报", "outlet_type": MediaOutletType.SERIOUS,
     "stance": MediaStance.NEUTRAL, "credibility": 88,
     "preferred_categories": ["boxoffice", "award_prediction", "industry_news"]},
    {"name": "星闻周刊", "outlet_type": MediaOutletType.TABLOID,
     "stance": MediaStance.HYPE, "credibility": 42,
     "preferred_categories": ["red_carpet", "controversy", "interview"]},
    {"name": "院线观察", "outlet_type": MediaOutletType.INDUSTRY,
     "stance": MediaStance.NEUTRAL, "credibility": 76,
     "preferred_categories": ["boxoffice", "industry_news"]},
]

# 事件 category -> 新闻类型（默认 BULLETIN）
CATEGORY_TO_NEWS_TYPE = {
    "票房": NewsType.BOXOFFICE,
    "奖项": NewsType.AWARD_PREDICTION,
    "电影节": NewsType.INDUSTRY_NEWS,
    "争议": NewsType.CONTROVERSY,
    "红毯": NewsType.RED_CARPET,
    "行业": NewsType.INDUSTRY_NEWS,
}

# 不同立场的语气词缀（仅影响模板文本观感，不影响任何事实数值）。
STANCE_FLAVOR = {
    MediaStance.NEUTRAL: "",
    MediaStance.POSITIVE: "令人欣喜的是，",
    MediaStance.CRITICAL: "值得注意的是，",
    MediaStance.HYPE: "惊爆！",
    MediaStance.SKEPTICAL: "冷静来看，",
}


def build_fact_pack(db: Session, world: World, event: Event) -> Dict[str, Any]:
    """从事件 + 相关实体聚合出结构化事实包。纯函数，无随机、无 IO。

    返回的 fact_pack 原样存入 news.fact_pack，未来可拿它重新渲染文本。

    Phase 5：召回相关人物的长期记忆与"世界记忆（行业气候）"作为报道背景，
    注入 memory_context。记忆仅用于丰富表达层文本，绝不参与任何判定（遵守 §11）。
    """
    store = MemoryStore(db, world)
    subjects: List[Dict[str, Any]] = []
    objects: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}

    for ent in (event.affected_entities or []):
        t, i = ent.get("type"), ent.get("id")
        if t == "character":
            c = db.get(Character, i)
            if c:
                subjects.append({
                    "type": "character", "id": c.id, "name": c.name,
                    "career_stage": c.career_stage.value if c.career_stage else None,
                })
        elif t == "project":
            p = db.get(Project, i)
            if p:
                objects.append({
                    "type": "project", "id": p.id, "title": p.title,
                    "project_type": p.type.value if p.type else None,
                })
                pm = (db.query(ProjectMarket)
                      .filter(ProjectMarket.project_id == p.id)
                      .order_by(ProjectMarket.id.desc()).first())
                if pm:
                    if pm.box_office is not None:
                        metrics["box_office"] = float(pm.box_office)
                    if pm.audience_score is not None:
                        metrics["audience_score"] = float(pm.audience_score)
                    if pm.media_score is not None:
                        metrics["media_score"] = float(pm.media_score)
                    if pm.outcome is not None:
                        metrics["outcome"] = pm.outcome.value

    # 因果因子统一为 [{factor, value}] 便于渲染与 LLM 消费
    causal_factors = []
    cc = event.causal_chain or {}
    if isinstance(cc, list):
        for item in cc:
            if isinstance(item, dict) and "factor" in item:
                causal_factors.append({"factor": item.get("factor"),
                                       "value": item.get("value")})
    elif isinstance(cc, dict):
        for k, v in cc.items():
            causal_factors.append({"factor": k, "value": v})

    summary = _summarize(event, subjects, objects)

    # ===== Phase 5：召回记忆作为报道背景（仅表达层）=====
    memory_context: List[Dict[str, Any]] = []
    for s in subjects:
        mems = store.recall(
            agent="character_agent", scope=MemoryScope.LONG,
            key_prefix=f"char:{s['id']}:", top_k=3, include_dormant=False)
        for m in mems:
            memory_context.append({
                "character_id": s["id"], "character_name": s["name"],
                "key": m.key, "value": m.value,
            })
    climate = store.recall_one(agent="world", scope=MemoryScope.WORLD, key="industry_climate")
    if climate:
        memory_context.append({
            "character_id": None, "character_name": None,
            "key": "industry_climate", "value": climate.value,
        })

    return {
        "event_id": event.id,
        "level": event.level.value if event.level else "normal",
        "category": event.category,
        "date": event.event_date.isoformat() if event.event_date else None,
        "subjects": subjects,
        "objects": objects,
        "metrics": metrics,
        "causal_factors": causal_factors,
        "memory_context": memory_context,
        "summary": summary,
    }


def _summarize(event: Event, subjects, objects) -> str:
    sub_names = "、".join(s["name"] for s in subjects) or "行业"
    obj_names = "、".join(o["title"] for o in objects)
    base = event.title or event.description or "影视圈发生新动态"
    if obj_names:
        return f"{sub_names} 相关作品《{obj_names}》：{base}"
    return f"{sub_names}：{base}"


def _should_report(event: Event) -> bool:
    """控制新闻量，使新闻密度与事件重要度正相关（防噪声）。"""
    lvl = event.level
    if lvl in (EventLevel.MAJOR, EventLevel.HISTORIC):
        return True
    if lvl == EventLevel.IMPORTANT:
        return True
    # NORMAL 事件本阶段不单独成稿，避免信息过载
    return False


def _classify_news_type(event: Event) -> NewsType:
    cat = event.category or ""
    # 负面奖项优先判定为争议（避免被 "奖项" 子串误判为奖项预测）
    if "负面" in cat:
        return NewsType.CONTROVERSY
    for key, ntype in CATEGORY_TO_NEWS_TYPE.items():
        if key in cat:
            return ntype
    return NewsType.BULLETIN


def _pick_outlet(event: Event, outlets: List[MediaOutlet], seed: int) -> MediaOutlet:
    """按新闻类别挑选最匹配的媒体；无匹配则回落到公信力最高的严肃媒体。"""
    ntype = _classify_news_type(event).value
    matched = [o for o in outlets if ntype in (o.preferred_categories or [])]
    if matched:
        # 确定性地在匹配媒体间选一家（避免每轮固定同一家）
        return matched[seed % len(matched)]
    serious = [o for o in outlets if o.outlet_type == MediaOutletType.SERIOUS]
    pool = serious or outlets
    return max(pool, key=lambda o: o.credibility)


def render_template(fact_pack: Dict[str, Any], outlet: MediaOutlet, news_type: NewsType) -> str:
    """模板渲染：所有数值都来自 fact_pack，立场仅影响语气。"""
    flavor = STANCE_FLAVOR.get(outlet.stance, "")
    date = fact_pack.get("date") or ""
    summary = fact_pack.get("summary") or ""
    metrics = fact_pack.get("metrics", {})
    return _render_body(fact_pack, outlet, news_type, flavor, date, summary, metrics)


def _memory_note(fact_pack: Dict[str, Any]) -> str:
    """从 memory_context 生成一句背景注脚（仅表达层，丰富文本，不干预任何判定）。"""
    ctx = fact_pack.get("memory_context") or []
    notes = []
    for c in ctx:
        key = c.get("key") or ""
        val = c.get("value") or {}
        if "honor" in key and isinstance(val, dict) and val.get("label"):
            who = c.get("character_name") or "该人物"
            notes.append(f"{who}曾凭{val.get('label')}留下高光记忆")
        elif "notorious" in key and isinstance(val, dict) and val.get("label"):
            who = c.get("character_name") or "该人物"
            notes.append(f"{who}曾因{val.get('label')}被点名，口碑争议犹在")
        elif "momentum" in key and isinstance(val, dict):
            d = val.get("delta") or 0
            if d > 0:
                who = c.get("character_name") or "该人物"
                notes.append(f"{who}近年人气持续走高")
        elif key == "industry_climate" and isinstance(val, dict):
            t = val.get("heat_trend")
            if t == 1:
                notes.append("业内整体人气处于回暖通道")
            elif t == -1:
                notes.append("业内整体人气有所降温")
    if not notes:
        return ""
    return "（背景：" + "；".join(notes[:2]) + "）"


def _render_body(fp, outlet, news_type, flavor, date, summary, metrics):
    subj = "、".join(s["name"] for s in fp.get("subjects", [])) or "业内"
    obj = "、".join(o["title"] for o in fp.get("objects", [])) or ""
    note = _memory_note(fp)
    if news_type == NewsType.BOXOFFICE and "box_office" in metrics:
        bo = metrics["box_office"]
        aud = metrics.get("audience_score")
        line = (f"【票房快讯】{date}，{obj}上映后票房达 {bo} 亿元"
                f"{f'，观众评分 {aud}' if aud is not None else ''}。"
                f"{flavor}{summary}")
        return line + note
    if news_type == NewsType.CONTROVERSY:
        return f"【娱乐风云】{date}，{flavor}{subj}卷入争议。{summary}" + note
    if news_type == NewsType.AWARD_PREDICTION:
        return f"【奖项观察】{date}，{flavor}{summary} 成为本届热门候选。" + note
    if news_type == NewsType.RED_CARPET:
        return f"【红毯直击】{date}，{flavor}{subj}亮相，引发热议。" + note
    # 默认快讯
    return f"【{fp.get('category') or '影视快讯'}】{date}，{flavor}{summary}" + note


class MediaAgent:
    """媒体 Agent：每个 tick 把本时段值得报道的事件转成新闻稿。"""

    def __init__(self, db: Session, world: World, tick: SimulationTick):
        self.db = db
        self.world = world
        self.tick = tick
        self.llm = get_llm_client()

    def run(self) -> int:
        outlets = (self.db.query(MediaOutlet)
                   .filter(MediaOutlet.world_id == self.world.id).all())
        if not outlets:
            outlets = self._seed_default_outlets()

        events = (self.db.query(Event)
                  .filter(Event.world_id == self.world.id,
                          Event.tick_id == self.tick.id).all())

        produced = 0
        for idx, ev in enumerate(events):
            if not _should_report(ev):
                continue
            outlet = _pick_outlet(ev, outlets, seed=(self.tick.tick_index + idx))
            news_type = _classify_news_type(ev)
            fact_pack = build_fact_pack(self.db, self.world, ev)
            body, engine, snapshot = self._render(fact_pack, outlet, news_type)
            self.db.add(News(
                world_id=self.world.id,
                outlet_id=outlet.id,
                tick_id=self.tick.id,
                primary_event_id=ev.id,
                related_event_ids=[ev.id],
                news_type=news_type,
                headline=self._headline(fact_pack, news_type),
                body=body,
                fact_pack=fact_pack,
                render_engine=engine,
                outlet_snapshot=snapshot,
                published_at=datetime.datetime.now(datetime.timezone.utc),
            ))
            produced += 1

        # 尖锐话题：负面奖项写入世界记忆 sharp_topics，媒体 Agent 在"后续"的 tick
        # 由八卦/毒舌媒体生成争议通稿（本 tick 刚写入的条目留到下一 tick，避免重复）。
        produced += self._generate_sharp_topic_news(outlets)
        return produced

    def _seed_default_outlets(self) -> List[MediaOutlet]:
        created = []
        for spec in DEFAULT_OUTLETS:
            o = MediaOutlet(
                world_id=self.world.id,
                name=spec["name"],
                outlet_type=spec["outlet_type"],
                stance=spec["stance"],
                credibility=spec["credibility"],
                preferred_categories=spec["preferred_categories"],
                founded_year=self.world.current_year,
            )
            self.db.add(o)
            created.append(o)
        self.db.flush()
        return created

    def _render(self, fact_pack, outlet, news_type):
        snapshot = {
            "stance": outlet.stance.value if outlet.stance else "neutral",
            "credibility": outlet.credibility,
            "outlet_type": outlet.outlet_type.value if outlet.outlet_type else "serious",
            "name": outlet.name,
        }
        try:
            text = self.llm.render_narrative(fact_pack, snapshot, news_type.value)
        except Exception:
            text = None
        if text:
            return text, RenderEngine.LLM, snapshot
        return render_template(fact_pack, outlet, news_type), RenderEngine.TEMPLATE, snapshot

    def _headline(self, fact_pack, news_type) -> str:
        prefix = {
            NewsType.BOXOFFICE: "票房",
            NewsType.CONTROVERSY: "争议",
            NewsType.AWARD_PREDICTION: "奖项",
            NewsType.RED_CARPET: "红毯",
            NewsType.INDUSTRY_NEWS: "行业",
        }.get(news_type, "快讯")
        return f"【{prefix}】{fact_pack.get('summary', '')[:40]}"

    # ===================== 尖锐话题（负面奖项 -> 争议通稿） =====================
    def _pick_sharp_outlet(self, outlets: List[MediaOutlet]) -> MediaOutlet:
        """尖锐话题优先交给八卦/毒舌媒体，制造"充满争议"的语气。"""
        for prefer in (MediaOutletType.TABLOID, MediaOutletType.INDUSTRY):
            matched = [o for o in outlets if o.outlet_type == prefer]
            if matched:
                return matched[0]
        return outlets[0] if outlets else None

    def _build_sharp_fact_pack(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        """把一条尖锐话题构造为合规 fact_pack（数值/陈述全部来自话题本身，零推断）。"""
        return {
            "event_id": None,
            "level": "major",
            "category": "负面奖项",
            "date": self.tick.to_date.date().isoformat(),
            "subjects": [],
            "objects": [],
            "metrics": {},
            "causal_factors": [],
            "memory_context": [],
            "summary": topic.get("headline", "某奖项揭晓引发热议"),
        }

    def _generate_sharp_topic_news(self, outlets: List[MediaOutlet]) -> int:
        """召回前序 tick 未消耗的 sharp_topics，生成争议通稿；本 tick 新写入的留到下一 tick。"""
        if not outlets:
            return 0
        store = MemoryStore(self.db, self.world)
        mem = store.recall_one("world", MemoryScope.WORLD, "sharp_topics")
        if not mem or not isinstance(mem.value, list):
            return 0
        topics = mem.value
        cur_tick = self.tick.tick_index
        pending = [t for t in topics
                   if (not t.get("consumed")) and (t.get("created_tick", 0) < cur_tick)]
        if not pending:
            return 0

        outlet = self._pick_sharp_outlet(outlets)
        produced = 0
        for topic in pending[:2]:  # 每 tick 最多 2 条，防刷屏
            fp = self._build_sharp_fact_pack(topic)
            body, engine, snapshot = self._render(fp, outlet, NewsType.CONTROVERSY)
            self.db.add(News(
                world_id=self.world.id,
                outlet_id=outlet.id,
                tick_id=self.tick.id,
                primary_event_id=None,
                related_event_ids=[],
                news_type=NewsType.CONTROVERSY,
                headline=f"【争议】{topic.get('headline', '')[:40]}",
                body=body,
                fact_pack=fp,
                render_engine=engine,
                outlet_snapshot=snapshot,
                published_at=datetime.datetime.now(datetime.timezone.utc),
            ))
            topic["consumed"] = True
            produced += 1

        # 裁剪：已消耗且较旧的条目移除，控制世界记忆体积（保留近 12 tick 内的历史）
        kept = [t for t in topics
                if not (t.get("consumed") and (cur_tick - t.get("created_tick", 0) > 12))]
        store.write_world("sharp_topics", kept, importance=0.95)
        return produced


# ===================== 报告聚合器 =====================
def _period_bounds(report_type: str, year: int, month: Optional[int], quarter: Optional[int]):
    """返回 (start_date, end_date) 闭区间（date 对象）。"""
    if report_type == ReportType.MONTHLY.value and month:
        start = datetime.date(year, month, 1)
        if month == 12:
            end = datetime.date(year, 12, 31)
        else:
            end = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    elif report_type == ReportType.QUARTERLY.value and quarter:
        m0 = (quarter - 1) * 3 + 1
        start = datetime.date(year, m0, 1)
        m1 = m0 + 3
        if m1 > 12:
            end = datetime.date(year, 12, 31)
        else:
            end = datetime.date(year, m1, 1) - datetime.timedelta(days=1)
    else:  # annual
        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)
    return start, end


def generate_report(db: Session, world: World, report_type: str,
                    year: int, month: Optional[int] = None,
                    quarter: Optional[int] = None) -> Dict[str, Any]:
    """聚合月/季/年报。所有数字来自数据库真实查询，保证与 world 一致。"""
    start, end = _period_bounds(report_type, year, month, quarter)
    label = (f"{year}年{month}月" if report_type == ReportType.MONTHLY.value and month
             else f"{year}年Q{quarter}" if report_type == ReportType.QUARTERLY.value and quarter
             else f"{year}年度")

    events = (db.query(Event)
              .filter(Event.world_id == world.id,
                      Event.event_date >= start, Event.event_date <= end)
              .all())
    released = (db.query(Project)
                .filter(Project.world_id == world.id,
                        Project.status == "released",
                        Project.release_year == year,
                        Project.release_month.isnot(None),
                        Project.release_month >= (month or 1),
                        Project.release_month <= ((month or 12) if report_type != ReportType.ANNUAL.value else 12))
                .all()) if report_type != ReportType.ANNUAL.value else (
                db.query(Project).filter(Project.world_id == world.id,
                                         Project.status == "released",
                                         Project.release_year == year).all())

    # 区间票房表现
    pm_rows = (db.query(ProjectMarket)
               .join(Project, ProjectMarket.project_id == Project.id)
               .filter(ProjectMarket.world_id == world.id,
                       Project.release_year == year,
                       Project.release_month.isnot(None))
               .all())
    pm_in = [pm for pm in pm_rows
             if (month is None or (Project.release_month and start.month <= Project.release_month <= end.month))
             and pm.box_office is not None]

    sections = []
    sections.append({"key": "period", "title": "报告周期", "value": label})
    sections.append({"key": "event_count", "title": "本周期事件数",
                     "value": len(events),
                     "detail": "；".join(e.title for e in events[:5])})

    top_box = max(pm_in, key=lambda pm: float(pm.box_office), default=None) if pm_in else None
    if top_box:
        proj = db.get(Project, top_box.project_id)
        sections.append({"key": "top_box_office", "title": "区间票房冠军",
                         "value": f"《{proj.title if proj else ''}》{float(top_box.box_office)}亿元"})

    majors = [e for e in events if e.level in (EventLevel.MAJOR.value, EventLevel.HISTORIC.value)]
    if majors:
        sections.append({"key": "major_events", "title": "重大事件回顾",
                         "value": len(majors),
                         "detail": "；".join(e.title for e in majors[:5])})

    controversies = [e for e in events if "争议" in (e.category or "")]
    if controversies:
        sections.append({"key": "controversy", "title": "本周期争议",
                         "value": "；".join(e.title for e in controversies[:3])})

    # 年报额外：年度作品总量与行业环境
    if report_type == ReportType.ANNUAL.value:
        sections.append({"key": "annual_releases", "title": "年度上映作品数",
                         "value": len(released)})
        from app.models.market import MarketSnapshot
        snap = (db.query(MarketSnapshot)
                .filter(MarketSnapshot.world_id == world.id)
                .order_by(MarketSnapshot.id.desc()).first())
        if snap:
            sections.append({"key": "market_env", "title": "行业环境",
                             "value": snap.environment or "未知",
                             "detail": snap.notes or ""})

    top_line = f"{label}共记录 {len(events)} 起事件" + (
        f"，票房冠军《{(db.get(Project, top_box.project_id).title if top_box and db.get(Project, top_box.project_id) else '')}》" if top_box else "")
    return {
        "world_id": world.id,
        "report_type": report_type,
        "year": year,
        "quarter": quarter,
        "period_label": label,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sections": sections,
        "top_line": top_line,
    }
