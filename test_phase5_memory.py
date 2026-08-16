"""Phase 5 记忆逻辑离线单测（不连库）。

仅校验"确定性衰减 / 检索权重 / 巩固阈值"这些纯计算部分——
数据库集成请在本地 Postgres 下用 run_smoke_test.py 验证。
"""
import math
import sys
import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/movie_world")

from app.models.enums import MemoryScope  # noqa: E402
from app.sim.memory import (  # noqa: E402
    MemoryStore, RECENCY_LAMBDA, FREQ_FACTOR, DORMANCY_FLOOR, CONSOLIDATE_THRESHOLD,
)


class _Stub:
    """最小记忆对象，仅承载 retrieval_weight 需要的字段（无需 ORM/DB）。"""
    def __init__(self, scope, importance=0.5, access_count=0, last_accessed_tick=0):
        self.scope = scope
        self.importance = importance
        self.access_count = access_count
        self.last_accessed_tick = last_accessed_tick


class _FakeWorld:
    total_ticks = 10


def test_world_memory_always_salient():
    store = MemoryStore(db=None, world=_FakeWorld())
    w = store.retrieval_weight(_Stub(MemoryScope.WORLD, importance=0.01, access_count=0, last_accessed_tick=0), 9999)
    assert w == 1.0, f"世界记忆权重应恒为 1.0，实际 {w}"


def test_recency_decay_is_deterministic_and_monotonic():
    store = MemoryStore(db=None, world=_FakeWorld())
    # 同重要度、同频率，越久未访问权重越低
    young = store.retrieval_weight(_Stub(MemoryScope.LONG, 0.5, 0, 0), 0)
    old = store.retrieval_weight(_Stub(MemoryScope.LONG, 0.5, 0, 0), 50)
    older = store.retrieval_weight(_Stub(MemoryScope.LONG, 0.5, 0, 0), 200)
    assert young > old > older, f"近因衰减应单调：{young},{old},{older}"
    # 公式与实现一致
    expected = 0.5 * math.exp(-RECENCY_LAMBDA * 50)
    assert abs(old - expected) < 1e-9


def test_frequency_boosts_weight():
    store = MemoryStore(db=None, world=_FakeWorld())
    once = store.retrieval_weight(_Stub(MemoryScope.LONG, 0.5, 0, 0), 10)
    many = store.retrieval_weight(_Stub(MemoryScope.LONG, 0.5, 10, 0), 10)
    assert many > once, f"高频访问应提升权重：{many} vs {once}"


def test_dormancy_floor():
    store = MemoryStore(db=None, world=_FakeWorld())
    # 极老 + 低重要度 -> 低于休眠阈值（会被 forget_step 标记休眠）
    weak = store.retrieval_weight(_Stub(MemoryScope.LONG, 0.1, 0, 0), 200)
    assert weak < DORMANCY_FLOOR, f"弱记忆权重应低于休眠阈值 {DORMANCY_FLOOR}，实际 {weak}"


def test_consolidate_threshold_meaning():
    # 巩固阈值用于区分"值得长期保留"与"仅短期草稿"
    assert CONSOLIDATE_THRESHOLD < 0.4, "短期重要记忆(>=0.4)应能巩固；草稿(<0.25)应过期清理"
    assert CONSOLIDATE_THRESHOLD > 0.15, "草稿(0.15)不应被巩固"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [OK ] {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\n{'✅ 全部通过' if failed == 0 else f'❌ {failed} 项失败'}")
    sys.exit(1 if failed else 0)
