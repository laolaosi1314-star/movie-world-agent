"""§17.1 商业时尚与塌房违约金：离线单测（不连库，确定性、可重放）。

覆盖：
  1. 枚举与权限矩阵（commerce:manage 仅 GM，属写类，受 423）；
  2. 纯函数：违约金计算 / 商业价值贬值系数；
  3. 桥接 §17.3：塌房 → 代言违约+违约金+商业价值重挫+封面取消+sharp_topics(commerce)；
  4. 自动商务生成：确定性、受 cap 限制、塌房人物不再接新约。
"""
import datetime as _dt

from app.models.enums import (
    EndorsementTier, ContractStatus, MagazineTier, CharacterType, CharacterStatus,
    PlayerRole, ScandalType, ScandalStage, WorldStatus,
)
from app.models.character import Character
from app.models.commerce import Endorsement, MagazineCover
from app.models.crisis import Scandal
from app.models.world import World, SimulationTick
from app.auth.roles import (
    PERM_COMMERCE_MANAGE, role_has_permission, WRITE_PERMISSIONS, capabilities_of,
)
from app.sim.commerce_agent import (
    compute_penalty, commercial_crash_factor, apply_collapse_penalty, CommercialAgent,
)


# ===================== 轻量 Fake DB（按模型类返回，过滤由 agent 在 Python 侧完成） =====================
FAKE_WRITES = []  # 全局捕获 MemoryStore.write_world 写入


class _FakeMemoryStore:
    def __init__(self, db, world):
        self.world = world
    def recall_one(self, agent, scope, key):
        return None
    def write_world(self, key, value, importance=None):
        FAKE_WRITES.append((key, value))
    def write_long(self, agent, key, value, importance=None):
        pass


class _FakeDB:
    def __init__(self, objs=None):
        self.objects = list(objs or [])
        self.added = []
        self._model = None
    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = _next_id()
        self.objects.append(obj)
    def flush(self):
        pass
    def query(self, model):
        self._model = model
        return self
    def filter(self, *args, **kw):
        return self
    def all(self):
        return [o for o in self.objects if isinstance(o, self._model)]
    def get(self, model, id_):
        for o in self.objects:
            if isinstance(o, model) and getattr(o, "id", None) == id_:
                return o
        return None


_id_counter = [0]
def _next_id():
    _id_counter[0] += 1
    return _id_counter[0]


def _patch_memory():
    """把 commerce/crisis Agent 内的 MemoryStore 替换为 fake，并清空写记录。"""
    import app.sim.commerce_agent as ca
    import app.sim.crisis_agent as cra
    ca.MemoryStore = _FakeMemoryStore
    cra.MemoryStore = _FakeMemoryStore
    FAKE_WRITES.clear()


# ===================== 测试夹具 =====================
def _make_world():
    w = World()
    w.id = 1
    w.current_year = 2026
    w.current_month = 1
    w.total_ticks = 5
    w.rng_seed = 0
    w.status = WorldStatus.ACTIVE
    w.industry_status = "平稳"
    return w


def _make_tick(index=5):
    return SimulationTick(
        id=None, world_id=1, tick_index=index, unit="quarter",
        from_date=_dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc),
        to_date=_dt.datetime(2026, 4, 1, tzinfo=_dt.timezone.utc), rng_seed_used=0,
    )


def _make_char(cid):
    c = Character()
    c.id = cid
    c.world_id = 1
    c.name = f"艺人{cid}"
    c.type = CharacterType.ACTOR
    c.status = CharacterStatus.ACTIVE
    c.attributes = {"heat": 95}
    c.commercial_value = 1000
    return c


# ===================== 1) 枚举与权限矩阵 =====================
def test_commerce_enums():
    assert {e.value for e in EndorsementTier} == {"top_luxury", "high_luxury", "mass", "brand_friend"}
    assert {e.value for e in ContractStatus} == {"active", "terminated", "breached", "expired"}
    assert {e.value for e in MagazineTier} == {"top5", "second_tier"}


def test_commerce_permission_matrix():
    assert role_has_permission(PlayerRole.GM, PERM_COMMERCE_MANAGE)
    assert not role_has_permission(PlayerRole.AUDIENCE, PERM_COMMERCE_MANAGE)
    assert not role_has_permission(PlayerRole.INVESTOR, PERM_COMMERCE_MANAGE)
    assert PERM_COMMERCE_MANAGE in WRITE_PERMISSIONS
    gm_caps = {a["key"] for a in capabilities_of(PlayerRole.GM)}
    assert "commerce:manage" in gm_caps
    aud_caps = {a["key"] for a in capabilities_of(PlayerRole.AUDIENCE)}
    assert "commerce:manage" not in aud_caps


# ===================== 2) 纯函数 =====================
def test_compute_penalty():
    assert compute_penalty(1000, 0.8, 12, 12) == 800   # 全剩余年限
    assert compute_penalty(1000, 0.8, 6, 12) == 400    # 半剩余
    assert compute_penalty(1000, 0.0, 12, 12) == 0     # 比例 0
    assert compute_penalty(1000, 0.8, -3, 12) == 0     # 剩余为负 → 封底 0


def test_crash_factor():
    assert 0.05 <= commercial_crash_factor(5) <= 1.0
    assert commercial_crash_factor(9) < commercial_crash_factor(5) < commercial_crash_factor(1)
    assert commercial_crash_factor(10) >= 0.05


# ===================== 3) 桥接 §17.3：塌房 → 商业崩塌 =====================
def test_collapse_triggers_breach_and_penalty():
    _patch_memory()
    char = _make_char(7)
    e1 = Endorsement(world_id=1, character_id=7, brand_name="Lumière 顶奢",
                     tier=EndorsementTier.TOP_LUXURY, annual_fee=1200, penalty_rate=0.8,
                     has_morals_clause=True, signed_tick=5, duration_ticks=12,
                     status=ContractStatus.ACTIVE)   # 本 tick 刚签 → 全剩余
    e2 = Endorsement(world_id=1, character_id=7, brand_name="Daily 饮品",
                     tier=EndorsementTier.MASS, annual_fee=200, penalty_rate=0.4,
                     has_morals_clause=True, signed_tick=4, duration_ticks=12,
                     status=ContractStatus.ACTIVE)   # 剩 11/12
    cov = MagazineCover(world_id=1, character_id=7, magazine_name="VOGUE 风尚",
                        tier=MagazineTier.TOP5, issue_tick=10, theme="封面",
                        fee=300, prestige=95, status=ContractStatus.ACTIVE)  # 未来封面
    cov_old = MagazineCover(world_id=1, character_id=7, magazine_name="ELLE 伊人",
                            tier=MagazineTier.TOP5, issue_tick=2, theme="封面",
                            fee=260, prestige=90, status=ContractStatus.ACTIVE)  # 已刊登
    scandal = Scandal(world_id=1, character_id=7, scandal_type=ScandalType.DRUGS,
                      title="某艺人吸毒", severity=9, evidence_strength=9,
                      is_confirmed=True, stage=ScandalStage.ERUPTED, heat=90,
                      public_opinion=5)

    db = _FakeDB([char, e1, e2, cov, cov_old, scandal])
    world = _make_world()
    tick = _make_tick(5)
    summary = apply_collapse_penalty(db, world, tick, char, scandal)

    assert e1.status == ContractStatus.BREACHED
    assert e2.status == ContractStatus.BREACHED
    assert e1.penalty_amount == 960   # 1200 * 0.8 * (全剩余 12/12)
    assert e2.penalty_amount == int(round(200 * 0.4 * 11 / 12))  # = 73
    assert summary["total_penalty"] == 960 + 73
    # 商业价值重挫（severity=9 → §17.1 因子 1-(0.6+0.27)=0.13 → 130）
    assert char.commercial_value == 130
    assert summary["commercial_value_after"] == 130
    # 未来封面取消，已刊登保留
    assert cov.status == ContractStatus.TERMINATED and cov.cancelled_tick == 5
    assert cov_old.status == ContractStatus.ACTIVE
    assert "VOGUE 风尚" in summary["cancelled_covers"]
    # 复用 §14：写 sharp_topics(domain=commerce)
    assert FAKE_WRITES, "应写入 sharp_topics"
    key, topics = FAKE_WRITES[0]
    assert key == "sharp_topics"
    assert topics[0]["domain"] == "commerce"
    assert "赔付违约金" in topics[0]["headline"]


def test_collapse_no_morals_clause_keeps_contract():
    _patch_memory()
    char = _make_char(7)
    e = Endorsement(world_id=1, character_id=7, brand_name="Trend 潮牌",
                    tier=EndorsementTier.BRAND_FRIEND, annual_fee=80, penalty_rate=0.3,
                    has_morals_clause=False, signed_tick=0, duration_ticks=12,
                    status=ContractStatus.ACTIVE)
    scandal = Scandal(world_id=1, character_id=7, scandal_type=ScandalType.AFFAIR,
                      title="x", severity=9, evidence_strength=9, is_confirmed=True,
                      stage=ScandalStage.ERUPTED, heat=90, public_opinion=5)
    db = _FakeDB([char, e, scandal])
    world = _make_world()
    tick = _make_tick(5)
    summary = apply_collapse_penalty(db, world, tick, char, scandal)
    assert e.status == ContractStatus.ACTIVE
    assert summary["total_penalty"] == 0
    assert summary["breaches"] == []


# ===================== 4) 自动商务生成（确定性、cap 限制） =====================
def _run_commerce(characters, extra=None):
    _patch_memory()
    db = _FakeDB(list(characters) + list(extra or []))
    world = _make_world()
    tick = _make_tick(5)
    n = CommercialAgent(db, world, tick).run()
    return db, n


def test_auto_sign_respects_cap():
    char = _make_char(1)  # heat=95
    db, n = _run_commerce([char])
    new_ends = [o for o in db.added if isinstance(o, Endorsement) and o.character_id == 1]
    assert len(new_ends) == 1  # 每 tick 至多签 1 个
    assert char.commercial_value == 1000  # 已初始化值不变


def test_auto_sign_skips_low_heat():
    char = _make_char(2)
    char.attributes = {"heat": 40}  # 低于阈值
    db, n = _run_commerce([char])
    new_ends = [o for o in db.added if isinstance(o, Endorsement)]
    assert len(new_ends) == 0


def test_collapsed_character_gets_no_new_deals():
    char = _make_char(3)  # heat=95
    scandal = Scandal(world_id=1, character_id=3, scandal_type=ScandalType.DRUGS,
                      title="塌房", severity=9, evidence_strength=9, is_confirmed=True,
                      stage=ScandalStage.COLLAPSED, heat=0, public_opinion=2)
    db, n = _run_commerce([char], extra=[scandal])
    new_ends = [o for o in db.added if isinstance(o, Endorsement)]
    assert len(new_ends) == 0
