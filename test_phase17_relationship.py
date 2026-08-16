"""§17.2 人际情感网络 + 人生档案馆：离线单测（不连库，确定性纯函数 + 轻量 FakeDB）。

覆盖：枚举/权限矩阵、fan_profile 确定性、compute_fan_reaction 粉丝蝴蝶效应、
RomanceAgent 演化（自然曝光→公开→结算；§17.3 出轨拆散）、§14 sharp_topics 复用、
人生档案馆聚合与历史注脚动态渲染。
"""
import sys
import datetime
import datetime as _dt

from app.models.enums import (
    RomanceType, RomanceStatus, CharacterType, ScandalType, ScandalStage,
)
from app.models.romance import Romance
from app.models.character import Character
from app.models.crisis import Scandal
from app.models.misc import Memory
from app.sim.romance_agent import (
    RomanceAgent, fan_profile, compute_fan_reaction, apply_romance_reaction,
)
from app.sim.life_archive import build_archive
from app.auth.roles import (
    PERM_RELATIONSHIP_MANAGE, capabilities_of, WRITE_PERMISSIONS,
)
from app.models.enums import PlayerRole


# ===================== Fake 基础设施 =====================
class _FakeWorld:
    def __init__(self):
        self.id = 1
        self.current_year = 2032
        self.current_month = 6
        self.total_ticks = 3
        self.status = "active"


class _FakeTick:
    def __init__(self, idx=3):
        self.id = 100 + idx
        self.tick_index = idx
        self.unit = "month"
        self.from_date = _dt.datetime(2032, 6, 1, tzinfo=_dt.timezone.utc)
        self.to_date = _dt.datetime(2032, 6, 30, tzinfo=_dt.timezone.utc)


class _FakeChar:
    def __init__(self, cid, ctype=CharacterType.ACTOR, heat=60, attrs=None):
        self.id = cid
        self.type = ctype
        self.status = "active"
        self.career_stage = "established"
        self.birth_year = None
        self.name = f"人物{cid}"
        self.attributes = dict(attrs or {})
        self.attributes.setdefault("heat", heat)
        self.commercial_value = None


class _FakeRomance:
    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.world_id = 1
        self.character_a_id = kw.get("a", 10)
        self.character_b_id = kw.get("b", 11)
        self.romance_type = kw.get("rtype", RomanceType.DATING)
        self.status = kw.get("status", RomanceStatus.ACTIVE)
        self.is_public = kw.get("is_public", False)
        self.publicness = kw.get("publicness", 0)
        self.reacted_tick = kw.get("reacted_tick")
        self.child_count = kw.get("child_count", 0)
        self.started_tick = kw.get("started_tick", 1)
        self.ended_tick = kw.get("ended_tick")
        self.ended_reason = kw.get("ended_reason")


class _FakeDB:
    def __init__(self):
        self.added = []
        self._rows = {}      # model -> list
        self._mem = {}       # (agent,scope,key) -> Memory
        self._get = {}       # id -> obj

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def get(self, model, pk):
        return self._get.get(pk)

    def query(self, model):
        self._qmodel = model
        return self

    def join(self, *args, **kw):
        return self

    def filter(self, *args, **kw):
        return self

    def order_by(self, *args, **kw):
        return self

    def all(self):
        return self._rows.get(self._qmodel, [])

    def first(self):
        rows = self._rows.get(self._qmodel, [])
        return rows[0] if rows else None

    def set_rows(self, model, rows):
        self._rows[model] = rows
        for r in rows:
            if hasattr(r, "id"):
                self._get[r.id] = r


class _FakeStore:
    """替代 MemoryStore：记录 world 记忆 sharp_topics 与 long 记忆。"""
    def __init__(self):
        self.world = {}
        self.long = {}

    def recall_one(self, agent, scope, key):
        if scope == "world":
            return self.world.get(key)
        return self.long.get((agent, key))

    def write_world(self, key, value, importance=None):
        self.world[key] = _M(value)

    def write_long(self, agent, key, value, importance=None):
        self.long[(agent, key)] = _M(value)


class _M:
    def __init__(self, value):
        self.value = value


def _make_agent(db, world, tick=None):
    # 注入 FakeStore 以绕过真实 MemoryStore
    import app.sim.romance_agent as ra
    agent = RomanceAgent(db, world, tick or _FakeTick())
    agent.store = _FakeStore()
    return agent


# ===================== 1. 枚举 / 权限矩阵 =====================
def test_enums_and_permissions():
    assert {e.value for e in RomanceType} == {"dating", "rumor", "married", "cohabit"}
    assert {e.value for e in RomanceStatus} == {"active", "ended"}
    gm_perms = {a["permission"] for a in capabilities_of(PlayerRole.GM)}
    assert PERM_RELATIONSHIP_MANAGE in gm_perms
    aud_perms = {a["permission"] for a in capabilities_of(PlayerRole.AUDIENCE)}
    assert PERM_RELATIONSHIP_MANAGE not in aud_perms
    assert PERM_RELATIONSHIP_MANAGE in WRITE_PERMISSIONS


# ===================== 2. 粉丝蝴蝶效应纯函数 =====================
def test_fan_profile_deterministic():
    idol = fan_profile(_FakeChar(1, CharacterType.SINGER))
    actor = fan_profile(_FakeChar(2, CharacterType.ACTOR))
    assert idol["idol_appeal"] > actor["idol_appeal"]
    # attributes 覆盖生效
    over = fan_profile(_FakeChar(3, CharacterType.ACTOR, attrs={"idol_appeal": 90}))
    assert over["idol_appeal"] == 90


def test_marriage_idol_defects_more():
    idol = fan_profile(_FakeChar(1, CharacterType.SINGER))
    mature = fan_profile(_FakeChar(2, CharacterType.ACTOR))
    r_idol = compute_fan_reaction(idol, "married", True, True)
    r_mature = compute_fan_reaction(mature, "married", True, True)
    assert r_idol["defect"] > r_mature["defect"]
    assert r_idol["backstab"] is True
    assert r_mature["backstab"] is False
    # 偶像结婚：脱粉 > 应援 → 净 heat 下滑
    assert r_idol["heat_delta"] < 0


def test_rumor_unconfirmed_only_buzz():
    idol = fan_profile(_FakeChar(1, CharacterType.SINGER))
    r = compute_fan_reaction(idol, "rumor", False, confirmed=False)
    assert r["defect"] == 0
    assert r["heat_delta"] > 0   # 吃瓜围观涨热度


def test_reaction_bounded():
    # 任意组合不越界
    for rtype in ("dating", "rumor", "married", "cohabit"):
        for ctype in (CharacterType.SINGER, CharacterType.ACTOR):
            res = compute_fan_reaction(fan_profile(_FakeChar(1, ctype)), rtype, True, True)
            assert -100 <= res["heat_delta"] <= 100


# ===================== 3. RomanceAgent 演化 =====================
def test_natural_leak_then_public_and_reaction():
    world = _FakeWorld()
    a = _FakeChar(10, CharacterType.SINGER, heat=80)
    b = _FakeChar(11, CharacterType.ACTOR, heat=60)
    rom = _FakeRomance(id=1, a=10, b=11, rtype=RomanceType.DATING,
                       is_public=False, publicness=55, started_tick=1)
    db = _FakeDB()
    db.set_rows(Character, [a, b])
    db.set_rows(Romance, [rom])
    agent = _make_agent(db, world, _FakeTick(3))
    agent.run()
    # publicness 55 + 6 = 61 >= 阈值 → 自动公开并结算
    assert rom.is_public is True
    assert rom.reacted_tick == 3
    # 歌手方应脱粉（heat 下降）
    assert a.attributes["heat"] < 80


def test_reaction_applied_once_only():
    world = _FakeWorld()
    a = _FakeChar(10, CharacterType.SINGER, heat=80)
    b = _FakeChar(11, CharacterType.ACTOR, heat=60)
    rom = _FakeRomance(id=1, a=10, b=11, rtype=RomanceType.DATING,
                       is_public=True, publicness=60, reacted_tick=2)
    db = _FakeDB()
    db.set_rows(Character, [a, b])
    db.set_rows(Romance, [rom])
    agent = _make_agent(db, world, _FakeTick(3))
    agent.run()
    # 已结算过 → 不重复结算（heat 不变；无新属性日志）
    assert a.attributes["heat"] == 80


def test_affair_scandal_breaks_romance():
    world = _FakeWorld()
    a = _FakeChar(10, CharacterType.SINGER, heat=80)
    b = _FakeChar(11, CharacterType.ACTOR, heat=60)
    rom = _FakeRomance(id=1, a=10, b=11, rtype=RomanceType.DATING,
                       is_public=True, publicness=80, reacted_tick=2)
    scandal = Scandal(world_id=1, character_id=10, scandal_type=ScandalType.AFFAIR,
                      title="出轨门", severity=9, evidence_strength=8,
                      is_confirmed=True, stage=ScandalStage.ERUPTED,
                      heat=90, public_opinion=10)
    db = _FakeDB()
    db.set_rows(Character, [a, b])
    db.set_rows(Romance, [rom])
    db.set_rows(Scandal, [scandal])
    agent = _make_agent(db, world, _FakeTick(3))
    agent.run()
    assert rom.status == RomanceStatus.ENDED
    assert rom.ended_reason and "出轨" in rom.ended_reason
    # 出轨方额外脱粉
    assert a.attributes["heat"] < 80


def test_sharp_topics_written_on_public():
    world = _FakeWorld()
    a = _FakeChar(10, CharacterType.SINGER, heat=80)
    b = _FakeChar(11, CharacterType.ACTOR, heat=60)
    rom = _FakeRomance(id=1, a=10, b=11, rtype=RomanceType.MARRIED,
                       is_public=False, publicness=58, started_tick=1)
    db = _FakeDB()
    db.set_rows(Character, [a, b])
    db.set_rows(Romance, [rom])
    agent = _make_agent(db, world, _FakeTick(3))
    agent.run()
    topics = agent.store.world.get("sharp_topics")
    assert topics is not None
    assert topics.value[0]["domain"] == "relationship"
    assert topics.value[0]["consumed"] is False


def test_apply_romance_reaction_out_of_tick():
    world = _FakeWorld()
    a = _FakeChar(10, CharacterType.SINGER, heat=80)
    b = _FakeChar(11, CharacterType.ACTOR, heat=60)
    rom = _FakeRomance(id=1, a=10, b=11, rtype=RomanceType.DATING,
                       is_public=True, publicness=60)
    db = _FakeDB()
    db.set_rows(Character, [a, b])
    db.set_rows(Romance, [rom])
    tick = _FakeTick(3)
    res = apply_romance_reaction(db, world, tick, rom, "恋情官宣")
    assert rom.reacted_tick == 3
    assert res["after"][10] < res["before"][10]   # 歌手脱粉


# ===================== 4. 人生档案馆聚合 =====================
def test_life_archive_aggregates_and_footnotes():
    world = _FakeWorld()
    char = _FakeChar(10, CharacterType.SINGER, heat=80)
    char.birth_year = 2000
    char.commercial_value = 500.0
    # 奖项
    from app.models.award import Winner, AwardSeason, Award
    from app.models.enums import AwardType
    award = Award(id=1, world_id=1, name="金屏奖", award_type=AwardType.POSITIVE,
                  domain="film")
    season = AwardSeason(id=1, award_id=1, season_number=1, year=2030, status="done")
    winner = Winner(id=1, season_id=1, category_id=1, category_name="最佳男主角",
                    character_id=10)
    # 商业
    from app.models.commerce import Endorsement
    end = Endorsement(id=1, world_id=1, character_id=10, brand_name="Lumière 顶奢",
                      category="腕表", tier="top_luxury", annual_fee=1200,
                      penalty_rate=0.8, has_morals_clause=True, signed_tick=12,
                      duration_ticks=12, status="active")
    # 丑闻
    scandal = Scandal(id=1, world_id=1, character_id=10, scandal_type=ScandalType.AFFAIR,
                      title="出轨门", severity=9, evidence_strength=8, is_confirmed=True,
                      stage=ScandalStage.COLLAPSED, heat=90, public_opinion=5,
                      exposed_tick=20, erupted_tick=22)
    # 情感
    rom = _FakeRomance(id=1, a=10, b=11, rtype=RomanceType.MARRIED,
                       is_public=True, publicness=80, reacted_tick=15, child_count=1)
    # 生涯
    from app.models.character import CharacterCareerHistory
    ch = CharacterCareerHistory(character_id=10, year=2028, month=1,
                                title="出道", description="首部作品")
    # 事件
    from app.models.event import Event
    from app.models.enums import EventLevel
    ev = Event(world_id=1, tick_id=22, event_date=_dt.date(2031, 3, 1),
               level=EventLevel.HISTORIC, category="丑闻争议", title="出轨门塌房",
               description="身败名裂", affected_entities=[{"type": "character", "id": 10}])
    # tick 映射
    from app.models.world import SimulationTick
    tick12 = SimulationTick(id=112, world_id=1, tick_index=12, unit="year",
                            from_date=_dt.datetime(2030, 1, 1, tzinfo=_dt.timezone.utc),
                            to_date=_dt.datetime(2030, 12, 31, tzinfo=_dt.timezone.utc))
    tick22 = SimulationTick(id=122, world_id=1, tick_index=22, unit="month",
                            from_date=_dt.datetime(2031, 3, 1, tzinfo=_dt.timezone.utc),
                            to_date=_dt.datetime(2031, 3, 31, tzinfo=_dt.timezone.utc))
    tick15 = SimulationTick(id=115, world_id=1, tick_index=15, unit="month",
                            from_date=_dt.datetime(2030, 6, 1, tzinfo=_dt.timezone.utc),
                            to_date=_dt.datetime(2030, 6, 30, tzinfo=_dt.timezone.utc))

    db = _FakeDB()
    db.set_rows(Character, [char])
    db.set_rows(Winner, [winner])
    db.set_rows(AwardSeason, [season])
    db.set_rows(Award, [award])
    db.set_rows(Endorsement, [end])
    db.set_rows(Scandal, [scandal])
    db.set_rows(Romance, [rom])
    db.set_rows(CharacterCareerHistory, [ch])
    db.set_rows(Event, [ev])
    db.set_rows(SimulationTick, [tick12, tick22, tick15])
    db._get.update({1: award, 1: season})  # award/season id=1
    db._get[112] = tick12
    db._get[122] = tick22
    db._get[115] = tick15

    arch = build_archive(db, world, char)
    assert arch["name"] == "人物10"
    assert arch["award_summary"]["total_wins"] == 1
    assert len(arch["awards"]) == 1
    assert len(arch["commercial"]) == 1
    assert len(arch["scandals"]) == 1
    assert len(arch["relationships"]) == 1
    assert len(arch["career_history"]) == 1
    assert len(arch["major_events"]) == 1
    assert len(arch["timeline"]) >= 4
    # 时间轴按年份升序
    years = [t["year"] for t in arch["timeline"] if t["year"]]
    assert years == sorted(years)


def test_archive_footnote_dynamic_from_memory():
    world = _FakeWorld()
    char = _FakeChar(10, CharacterType.SINGER, heat=80)
    db = _FakeDB()
    db.set_rows(Character, [char])
    # 写入长期记忆：notorious 注脚（模拟 §17.3 塌房后沉淀）
    store = _FakeStore()
    store.long[("character_agent", "char:10:notorious")] = _M(
        {"label": "因出轨丑闻塌房", "collapsed": True, "opinion": 5})
    # 把 store 注入 build_archive 使用的 MemoryStore：monkey-patch 模块
    import app.sim.life_archive as la
    orig = la.MemoryStore
    la.MemoryStore = lambda db, w: store
    try:
        arch = build_archive(db, world, char)
    finally:
        la.MemoryStore = orig
    assert any(f["kind"] == "notorious" for f in arch["legacy_footnotes"])
    note = [f for f in arch["legacy_footnotes"] if f["kind"] == "notorious"][0]
    assert note["text"] == "因出轨丑闻塌房"
