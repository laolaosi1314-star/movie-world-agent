"""§17.3 舆论与危机公关 —— 离线单测（不连库）。

覆盖：
  1. 枚举 / 模型列 / 权限矩阵（crisis:manage 归 GM、不归观众、属写类）；
  2. 多阶段公关确定性结算 evaluate_pr 的胜负手矩阵（冷处理/律师函/道歉/买热搜/洗白反转）；
  3. 丑闻演化状态机（潜伏 / 发酵→爆发 / 确定性舆论恢复曲线）；
  4. §14 闭环复用：爆发时写入世界记忆 sharp_topics（与负面奖项同源，供媒体 Agent 生成争议通稿）；
  5. _badness 桥接：scandal_reputation_penalty 把实锤丑闻喂入负奖烂度。
"""
import sys
import datetime as _dt

import pytest
from app.models.enums import (
    PlayerRole, ScandalType, ScandalStage, PRStrategy, MemoryScope,
)
from app.models import enums as _E
from app.auth import roles as R
from app.sim import crisis_agent as CA
from app.schemas.crisis import ScandalCreate, ScandalOut, PRStrategyIn, CrisisPROut


# ---------- 1. 枚举 / 模型 / 权限 ----------
def test_crisis_enums():
    assert {e.value for e in ScandalType} == {
        "affair", "drugs", "tax", "slip_of_tongue", "surrogacy",
        "plagiarism", "domestic_violence", "other"}
    assert {e.value for e in ScandalStage} == {
        "latent", "spreading", "erupted", "resolving", "resolved", "collapsed"}
    assert {e.value for e in PRStrategy} == {
        "cold_treatment", "lawyer_letter", "apology", "buy_trending", "counter_mkt"}


def test_crisis_permission_matrix():
    assert R.PERM_CRISIS_MANAGE in {a["permission"] for a in R.capabilities_of(PlayerRole.GM)}
    assert R.PERM_CRISIS_MANAGE not in {a["permission"] for a in R.capabilities_of(PlayerRole.AUDIENCE)}
    assert R.PERM_CRISIS_MANAGE not in {a["permission"] for a in R.capabilities_of(PlayerRole.INVESTOR)}
    assert R.PERM_CRISIS_MANAGE in R.WRITE_PERMISSIONS
    keys = {a["key"] for a in R.ACTION_CATALOG}
    assert "crisis:manage" in keys


def test_crisis_schemas_validate():
    s = ScandalCreate(character_id=1, title="某明星出轨", scandal_type="affair",
                      severity=7, exposed=True)
    assert s.severity == 7 and s.scandal_type == "affair"
    p = PRStrategyIn(strategy="apology", note="公开致歉")
    assert p.strategy == "apology"
    assert ScandalOut is not None and CrisisPROut is not None


# ---------- 2. 公关确定性结算矩阵 ----------
def test_cold_treatment_cools_heat():
    r = CA.evaluate_pr(PRStrategy.COLD_TREATMENT, 5, 5, False, ScandalStage.SPREADING)
    assert r["delta_heat"] < 0           # 降温
    assert abs(r["delta_opinion"]) <= 3  # 不直接扭转口碑


def test_lawyer_letter_weak_evidence_ok_confirmed_backfires():
    weak = CA.evaluate_pr(PRStrategy.LAWYER_LETTER, 6, 2, False, ScandalStage.ERUPTED)
    assert weak["delta_opinion"] > 0      # 证据弱→维权成功
    confirmed = CA.evaluate_pr(PRStrategy.LAWYER_LETTER, 6, 9, True, ScandalStage.ERUPTED)
    assert confirmed["delta_opinion"] < 0  # 实锤还发函→捂嘴反感


def test_apology_confirmed_ok_unconfirmed_backfires():
    confirmed = CA.evaluate_pr(PRStrategy.APOLOGY, 6, 9, True, ScandalStage.ERUPTED)
    assert confirmed["delta_opinion"] > 0   # 实锤认错→公众接受
    unconfirmed = CA.evaluate_pr(PRStrategy.APOLOGY, 6, 2, False, ScandalStage.ERUPTED)
    assert unconfirmed["delta_opinion"] < 0  # 未实锤却道歉→变相认锤


def test_buy_trending_decay_only_slightly_negative():
    r = CA.evaluate_pr(PRStrategy.BUY_TRENDING, 5, 5, False, ScandalStage.SPREADING)
    assert r["decay_only"] is True
    assert r["delta_opinion"] <= 0          # 口碑略负


def test_counter_mkt_weak_flips_confirmed_collapses():
    weak = CA.evaluate_pr(PRStrategy.COUNTER_MKT, 8, 2, False, ScandalStage.ERUPTED)
    assert weak["delta_opinion"] > 0        # 证据弱→洗白大翻盘
    confirmed = CA.evaluate_pr(PRStrategy.COUNTER_MKT, 8, 9, True, ScandalStage.ERUPTED)
    assert confirmed["delta_opinion"] < 0   # 实锤强行洗白→塌房加速


def test_severity_scales_pr_magnitude():
    lo = CA.evaluate_pr(PRStrategy.COUNTER_MKT, 1, 2, False, ScandalStage.ERUPTED)
    hi = CA.evaluate_pr(PRStrategy.COUNTER_MKT, 10, 2, False, ScandalStage.ERUPTED)
    assert abs(hi["delta_opinion"]) > abs(lo["delta_opinion"])  # 越严重摆幅越大


def test_eruption_drop_and_recovery_target_bounds():
    assert CA.compute_eruption_drop(10, 10, True) <= 60   # 封顶
    assert CA.compute_eruption_drop(1, 1, False) >= 0
    assert 8 <= CA.natural_recovery_target(10) <= 50      # 严重丑闻难完全恢复
    assert CA.natural_recovery_target(1) == 48


# ---------- 3. 丑闻演化状态机（离线，桩 DB + 桩 MemoryStore） ----------
class _FakeScandal:
    """最小丑闻对象（仅承载 CrisisAgent 读写用的属性，不依赖 ORM）。"""
    def __init__(self, **kw):
        self.id = kw.get("id", 1)
        self.world_id = kw.get("world_id", 1)
        self.character_id = kw.get("character_id", 1)
        self.scandal_type = kw.get("scandal_type", ScandalType.AFFAIR)
        self.title = kw.get("title", "测试丑闻")
        self.severity = kw.get("severity", 5)
        self.evidence_strength = kw.get("evidence_strength", 5)
        self.is_confirmed = kw.get("is_confirmed", False)
        self.stage = kw.get("stage", ScandalStage.LATENT)
        self.heat = kw.get("heat", 0)
        self.public_opinion = kw.get("public_opinion", 50)
        self.exposed_tick = kw.get("exposed_tick", None)
        self.erupted_tick = kw.get("erupted_tick", None)
        self.resolved_tick = kw.get("resolved_tick", None)


class _FakeMemoryStore:
    """记录 CrisisAgent 对世界记忆的写入（验证 §14 sharp_topics 复用）。"""
    def __init__(self, db, world):
        self.db = db
        self.world = world

    def recall_one(self, agent, scope, key):
        return None  # 视为首次写入

    def write_world(self, key, value, importance=None):
        self.db.sharp_writes.append((key, value))

    def write_long(self, agent, key, value, importance=None):
        pass


class _FakeDB:
    def __init__(self, scandal_rows=None):
        self.added = []
        self.sharp_writes = []
        self._scandal_rows = scandal_rows or []
        self._confirmed_only = False
        self._model = None

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def query(self, model):
        self._model = model
        return self

    def filter(self, *args, **kw):
        # 桩：识别 Scandal.is_confirmed.is_(True) 以便真实模拟"仅实锤"分支
        for arg in args:
            left = getattr(arg, "left", None)
            if getattr(left, "name", None) == "is_confirmed":
                self._confirmed_only = True
        return self

    def all(self):
        # 非 Scandal 查询（§17.1 桥接时的 Endorsement/MagazineCover）返回空，避免属性错误
        if self._model is not None and getattr(self._model, "__name__", "") != "Scandal":
            return []
        rows = self._scandal_rows
        if self._confirmed_only:
            rows = [r for r in rows if getattr(r, "is_confirmed", False)]
        return rows

    def get(self, model, id_):
        # §17.1 桥接：塌房时 CrisisAgent 取人物以结算商业崩塌；桩默认无人物 → 跳过
        return None


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(CA, "MemoryStore", _FakeMemoryStore)
    world = type("W", (), {"id": 1, "total_ticks": 0})()
    db = _FakeDB()
    return world, db


def _make_agent(world, db, tick_index):
    tick = type("T", (), {
        "id": 1, "tick_index": tick_index,
        "to_date": _dt.datetime(2032, 1, 1, tzinfo=_dt.timezone.utc),
    })()
    return CA.CrisisAgent(db, world, tick)


def test_latent_stays_latent(patched):
    world, db = patched
    s = _FakeScandal(stage=ScandalStage.LATENT, heat=5)
    agent = _make_agent(world, db, 0)
    agent._evolve(s)
    assert s.stage == ScandalStage.LATENT


def test_spreading_erupts_after_threshold_and_writes_sharp(patched):
    world, db = patched
    s = _FakeScandal(stage=ScandalStage.SPREADING, exposed_tick=0,
                     severity=5, evidence_strength=5, is_confirmed=False,
                     heat=45, public_opinion=50)
    agent = _make_agent(world, db, 1)
    agent._evolve(s)  # age=1 < 2 → 仍发酵
    assert s.stage == ScandalStage.SPREADING
    agent2 = _make_agent(world, db, 2)
    agent2._evolve(s)  # age=2 → 爆发
    assert s.stage == ScandalStage.ERUPTED
    assert s.erupted_tick == 2
    # tick=1 发酵步 opinion 50→49，tick=2 爆发再扣 15 → 34
    assert s.public_opinion == 34
    # 爆发事件被写入（媒体 Agent 按 category 含"争议"生成 CONTROVERSY 新闻）
    events = [a for a in db.added if getattr(a, "__tablename__", None) == "events"]
    assert any("引爆" in (e.title or "") for e in events)


def test_sharp_topics_written_on_eruption(patched):
    world, db = patched  # patched fixture 已将 MemoryStore 替换为 _FakeMemoryStore
    s = _FakeScandal(stage=ScandalStage.SPREADING, exposed_tick=0,
                     severity=6, evidence_strength=4, is_confirmed=False,
                     heat=45, public_opinion=50)
    agent = _make_agent(world, db, 2)
    agent._emit_sharp(s, 2)  # 直接验证 §14 复用写入形状
    assert db.sharp_writes, "应写入 sharp_topics"
    key, topics = db.sharp_writes[0]
    assert key == "sharp_topics"
    assert topics[0]["headline"].startswith("丑闻：")
    assert topics[0]["consumed"] is False
    assert topics[0]["created_tick"] == 2


def test_confirmed_severe_collapse(patched):
    world, db = patched
    s = _FakeScandal(stage=ScandalStage.ERUPTED, is_confirmed=True, severity=9,
                     evidence_strength=9, heat=0, public_opinion=4)
    agent = _make_agent(world, db, 5)
    agent._evolve(s)
    assert s.stage == ScandalStage.COLLAPSED


# ---------- 4. _badness 桥接 ----------
def test_reputation_penalty_feeds_badness():
    db = _FakeDB(scandal_rows=[_FakeScandal(
        character_id=1, stage=ScandalStage.ERUPTED, is_confirmed=True,
        public_opinion=20, severity=8)])
    world = type("W", (), {"id": 1})()
    pen = CA.scandal_reputation_penalty(db, world, 1)
    # (50-20)*0.4 + 8*0.5 = 12 + 4 = 16
    assert abs(pen - 16.0) < 1e-6


def test_reputation_penalty_none_for_unconfirmed():
    db = _FakeDB(scandal_rows=[_FakeScandal(
        character_id=1, stage=ScandalStage.ERUPTED, is_confirmed=False,
        public_opinion=10, severity=9)])
    world = type("W", (), {"id": 1})()
    assert CA.scandal_reputation_penalty(db, world, 1) == 0.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
