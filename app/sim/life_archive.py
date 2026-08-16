"""人生档案馆（LifeArchive）：角色历史履历与时间轴的结构化聚合（只读）。

设计原则（与全局蓝图一致）：
  - 零新建表：纯聚合接口，从既有 awards / endorsements / scandals / romances / career_history
    / events / 长期记忆 中按人物结构化留痕；
  - 可重放、确定性：所有数字来自数据库真实查询，与 world 一致；
  - 「重大历史事件随岁月沉淀动态渲染」：legacy_footnotes 直接读取人物长期记忆
    （notorious 塌房注脚 / commercial 商业崩塌 / honor 奖项荣誉），记忆随 tick 沉淀，
    故同一人物在不同时点的档案馆呈现会动态变化（如塌房后自动带出"曾因丑闻塌房"）。

复用 §14/§17.1/§17.3 的记忆键，不改动任何写入方。
"""
from typing import Optional

from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.character import Character, CharacterCareerHistory
from app.models.enums import MemoryScope, AwardType
from app.models.award import Winner, Nomination, AwardSeason, Award, AwardAchievement
from app.models.commerce import Endorsement, MagazineCover
from app.models.crisis import Scandal
from app.models.romance import Romance
from app.models.event import Event
from app.models.misc import Memory
from app.sim.memory import MemoryStore


def _year_for_tick(db: Session, world: World, tick_index: Optional[int]) -> Optional[int]:
    """tick 索引 → 年份（确定性）。优先查 SimulationTick，否则按世界当前进度线性回推。"""
    if tick_index is None:
        return None
    t = (db.query(SimulationTick)
         .filter(SimulationTick.world_id == world.id,
                 SimulationTick.tick_index == tick_index).first())
    if t and t.to_date is not None:
        return t.to_date.year
    if world.total_ticks and tick_index <= world.total_ticks:
        # 约 12 tick/年，从当前年份回推
        return world.current_year - max(0, (world.total_ticks - tick_index)) // 12
    return world.current_year


def _name(db: Session, cid: Optional[int]) -> Optional[str]:
    if cid is None:
        return None
    c = db.get(Character, cid)
    return c.name if c else f"人物{cid}"


def build_archive(db: Session, world: World, character: Character) -> dict:
    """聚合某人物的一生档案。返回结构化 dict（供 LifeArchiveOut 包装）。"""
    cid = character.id
    attrs = character.attributes or {}
    heat = int(attrs.get("heat", 50))

    # ---------- 奖项 ----------
    awards = []
    winners = (
        db.query(Winner).join(AwardSeason, Winner.season_id == AwardSeason.id)
        .filter(Winner.character_id == cid).all()
    )
    for w in winners:
        season = db.get(AwardSeason, w.season_id)
        award = db.query(Award).filter(Award.id == season.award_id).first() if season else None
        awards.append({
            "year": season.year if season else None,
            "award": award.name if award else None,
            "award_type": award.award_type.value if award and award.award_type else None,
            "category": w.category_name,
            "result": "win",
            "subject": _name(db, w.character_id),
        })
    noms = (
        db.query(Nomination).join(AwardSeason, Nomination.season_id == AwardSeason.id)
        .filter(Nomination.character_id == cid).all()
    )
    for n in noms:
        if any(a["category"] == n.category_name and a["result"] == "win" for a in awards):
            continue  # 已获奖者不再重复列为提名
        season = db.get(AwardSeason, n.season_id)
        award = db.query(Award).filter(Award.id == season.award_id).first() if season else None
        awards.append({
            "year": season.year if season else None,
            "award": award.name if award else None,
            "award_type": award.award_type.value if award and award.award_type else None,
            "category": n.category_name,
            "result": "nomination",
            "subject": _name(db, n.character_id),
        })
    achievements = (
        db.query(AwardAchievement).filter(AwardAchievement.character_id == cid).all()
    )
    award_summary = {
        "total_wins": sum(1 for a in awards if a["result"] == "win"),
        "total_nominations": sum(1 for a in awards if a["result"] == "nomination"),
        "achievements": [{"award": (db.query(Award).filter(Award.id == ac.award_id).first().name
                                   if db.query(Award).filter(Award.id == ac.award_id).first() else None),
                          "note": ac.note} for ac in achievements],
    }

    # ---------- 商业（§17.1） ----------
    endorsements = db.query(Endorsement).filter(Endorsement.character_id == cid).all()
    comm = []
    for e in endorsements:
        comm.append({
            "year": _year_for_tick(db, world, e.signed_tick),
            "kind": "endorsement",
            "name": e.brand_name,
            "tier": e.tier.value if hasattr(e.tier, "value") else str(e.tier),
            "status": e.status.value if hasattr(e.status, "value") else str(e.status),
            "annual_fee": e.annual_fee,
            "penalty_amount": e.penalty_amount,
        })
    covers = db.query(MagazineCover).filter(MagazineCover.character_id == cid).all()
    for c in covers:
        comm.append({
            "year": _year_for_tick(db, world, c.issue_tick),
            "kind": "cover",
            "name": c.magazine_name,
            "tier": c.tier.value if hasattr(c.tier, "value") else str(c.tier),
            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
            "fee": c.fee,
        })

    # ---------- 丑闻（§17.3） ----------
    scandals = db.query(Scandal).filter(Scandal.character_id == cid).all()
    scan = []
    for s in scandals:
        scan.append({
            "year": _year_for_tick(db, world, s.erupted_tick or s.exposed_tick),
            "type": s.scandal_type.value if hasattr(s.scandal_type, "value") else str(s.scandal_type),
            "title": s.title,
            "stage": s.stage.value if hasattr(s.stage, "value") else str(s.stage),
            "severity": s.severity,
            "is_confirmed": s.is_confirmed,
        })

    # ---------- 情感（§17.2） ----------
    romances = db.query(Romance).filter(
        (Romance.character_a_id == cid) | (Romance.character_b_id == cid)).all()
    rel = []
    for r in romances:
        partner_id = r.character_b_id if r.character_a_id == cid else r.character_a_id
        rel.append({
            "year": _year_for_tick(db, world, r.started_tick),
            "type": r.romance_type.value if hasattr(r.romance_type, "value") else str(r.romance_type),
            "partner": _name(db, partner_id),
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "is_public": r.is_public,
            "child_count": r.child_count,
            "ended_reason": r.ended_reason,
        })

    # ---------- 生涯时间线（CharacterCareerHistory） ----------
    careers = db.query(CharacterCareerHistory).filter(
        CharacterCareerHistory.character_id == cid).order_by(
        CharacterCareerHistory.year, CharacterCareerHistory.month).all()
    career = [{"year": c.year, "month": c.month, "title": c.title,
               "description": c.description} for c in careers]

    # ---------- 重大事件（Event 表中影响本人物者） ----------
    events = db.query(Event).filter(Event.world_id == world.id).all()
    major_events = []
    for ev in events:
        ents = ev.affected_entities or []
        if any(e.get("type") == "character" and e.get("id") == cid for e in ents):
            major_events.append({
                "tick": ev.tick_id,
                "year": ev.event_date.year if ev.event_date else None,
                "level": ev.level.value if ev.level else None,
                "category": ev.category,
                "title": ev.title,
                "description": ev.description,
            })

    # ---------- 时间轴（合并排序，随岁月沉淀） ----------
    timeline = _build_timeline(awards, comm, scan, rel, career, major_events)

    # ---------- 历史注脚（动态渲染：来自长期记忆，随 tick 沉淀） ----------
    legacy_footnotes = _build_legacy_footnotes(db, world, cid)

    return {
        "character_id": cid,
        "name": character.name,
        "type": character.type.value if hasattr(character.type, "value") else str(character.type),
        "birth_year": character.birth_year,
        "career_stage": character.career_stage.value if hasattr(character.career_stage, "value")
        else str(character.career_stage),
        "status": character.status.value if hasattr(character.status, "value") else str(character.status),
        "heat": heat,
        "commercial_value": (float(character.commercial_value)
                             if character.commercial_value is not None else None),
        "award_summary": award_summary,
        "awards": sorted([a for a in awards if a["year"]], key=lambda x: x["year"]),
        "commercial": sorted([c for c in comm if c["year"]], key=lambda x: x["year"]),
        "scandals": sorted([s for s in scan if s["year"]], key=lambda x: x["year"]),
        "relationships": sorted([r for r in rel if r["year"]], key=lambda x: x["year"]),
        "career_history": career,
        "major_events": sorted(major_events, key=lambda x: (x["tick"] or 0)),
        "timeline": timeline,
        "legacy_footnotes": legacy_footnotes,
    }


def _build_timeline(awards, comm, scan, rel, career, major_events) -> list:
    """把各维度事件合并为统一时间轴（按年份升序，同年按类型权重）。"""
    items = []
    for a in awards:
        if a["year"]:
            items.append({"year": a["year"], "kind": "award",
                          "title": f"{'荣获' if a['result'] == 'win' else '提名'}"
                                   f"{a['award']}·{a['category']}",
                          "detail": f"结果：{a['result']}",
                          "significance": 3 if a["result"] == "win" else 1})
    for c in comm:
        if c["year"]:
            label = "代言" if c["kind"] == "endorsement" else "封面"
            items.append({"year": c["year"], "kind": "commercial",
                          "title": f"签约{label}：{c['name']}",
                          "detail": f"状态：{c['status']}",
                          "significance": 1})
    for s in scan:
        if s["year"]:
            items.append({"year": s["year"], "kind": "scandal",
                          "title": f"丑闻：{s['title']}",
                          "detail": f"阶段：{s['stage']}（严重度{s['severity']}）",
                          "significance": 4 if s["stage"] == "collapsed" else 3})
    for r in rel:
        if r["year"]:
            items.append({"year": r["year"], "kind": "relationship",
                          "title": f"与{r['partner']}的{r['type']}"
                                   + ("公开" if r["is_public"] else "（地下）"),
                          "detail": f"状态：{r['status']}"
                                    + (f"，子女{r['child_count']}人" if r["child_count"] else ""),
                          "significance": 2})
    for c in career:
        if c["year"]:
            items.append({"year": c["year"], "kind": "career",
                          "title": c["title"], "detail": c["description"] or "",
                          "significance": 1})
    for e in major_events:
        if e["year"]:
            items.append({"year": e["year"], "kind": "event",
                          "title": e["title"], "detail": e["description"] or "",
                          "significance": 3 if e["level"] in ("major", "historic") else 1})
    items.sort(key=lambda x: (x["year"], -x["significance"]))
    return items


def _build_legacy_footnotes(db: Session, world: World, cid: int) -> list:
    """动态历史注脚：读取人物长期记忆，随 tick 沉淀自然呈现（如塌房后自动带出注脚）。"""
    store = MemoryStore(db, world)
    footnotes = []
    for key in (f"char:{cid}:notorious", f"char:{cid}:commercial", f"char:{cid}:honor"):
        mem = store.recall_one("character_agent", MemoryScope.LONG, key)
        if mem and isinstance(mem.value, dict):
            v = mem.value
            if "notorious" in key and v.get("label"):
                footnotes.append({"kind": "notorious", "text": v["label"],
                                  "collapsed": v.get("collapsed", False)})
            elif "commercial" in key and v.get("collapsed"):
                footnotes.append({"kind": "commercial",
                                  "text": f"曾因塌房致商业帝国崩塌，赔付违约金约{v.get('total_penalty')}万"})
            elif "honor" in key and v.get("label"):
                footnotes.append({"kind": "honor", "text": f"高光：{v['label']}"})
    return footnotes
