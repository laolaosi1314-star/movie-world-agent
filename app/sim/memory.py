"""Phase 5 记忆引擎：三层记忆（短期/长期/世界）的写入、检索、巩固与衰减。

设计原则（与全局蓝图一致）：
  - 确定性：遗忘曲线是 tick 索引的确定性函数（无 random），可重放、可解释。
  - 不污染判定：记忆只影响"偏置/上下文"，不替代因果规则；LLM 约束（§11）不受影响。
  - 历史不丢：短期记忆按时效物理清理；长期记忆仅标记"休眠"而保留，强线索可唤回。
  - 多世界隔离：所有查询按 world_id 过滤。

三层语义：
  short：单 tick 工作草稿，ttl/expires_tick 到点物理删除；
  long ：跨 tick 持久记忆，由"巩固"从短期提升而来，受遗忘曲线衰减；
  world：全 Agent 共享的世界集体知识，永不衰减、永不休眠。

检索权重 = importance × 近因因子(exp(-λ·age)) × 频率因子(1 + k·ln(1+access_count))
"""
import math
from sqlalchemy import or_

from app.models.misc import Memory
from app.models.enums import MemoryScope

# ===== 衰减与巩固超参（确定性，可重放）=====
RECENCY_LAMBDA = 0.03        # 每 tick 的近因衰减系数（越大忘得越快）
FREQ_FACTOR = 0.15           # 频率因子增益
DORMANCY_FLOOR = 0.08        # 长期记忆检索权重跌破此值 -> 休眠
CONSOLIDATE_THRESHOLD = 0.25 # 短期记忆重要度达标才巩固为长期
DEFAULT_SHORT_TTL = 3        # 短期记忆默认存活 tick 数


class MemoryStore:
    """面向单个 world 的记忆读写与维护入口。"""

    def __init__(self, db, world):
        self.db = db
        self.world = world

    @property
    def current_tick(self) -> int:
        return self.world.total_ticks

    # ---------------- 写入（按 world_id+agent+scope+key upsert）----------------
    def write(self, scope: MemoryScope, agent: str, key: str, value,
              importance: float = 0.5, ttl_ticks: int = None, expires_at=None):
        cur = self.current_tick
        existing = self._find(scope, agent, key)
        if existing:
            existing.value = value
            existing.importance = importance
            existing.last_accessed_tick = cur
            existing.access_count = (existing.access_count or 0) + 1
            existing.is_dormant = False
            if scope == MemoryScope.SHORT:
                existing.expires_tick = cur + (ttl_ticks or DEFAULT_SHORT_TTL)
                existing.expires_at = expires_at
            mem = existing
        else:
            mem = Memory(
                world_id=self.world.id,
                agent=agent,
                scope=scope,
                key=key,
                value=value,
                importance=importance,
                access_count=1,
                last_accessed_tick=cur,
                expires_tick=(cur + (ttl_ticks or DEFAULT_SHORT_TTL))
                if scope == MemoryScope.SHORT else None,
                expires_at=expires_at,
                is_dormant=False,
            )
            self.db.add(mem)
        self.db.flush()
        return mem

    def write_short(self, agent: str, key: str, value,
                    ttl_ticks: int = DEFAULT_SHORT_TTL, importance: float = 0.4):
        return self.write(MemoryScope.SHORT, agent, key, value,
                          importance=importance, ttl_ticks=ttl_ticks)

    def write_long(self, agent: str, key: str, value, importance: float = 0.6):
        return self.write(MemoryScope.LONG, agent, key, value, importance=importance)

    def write_world(self, key: str, value, importance: float = 0.8):
        return self.write(MemoryScope.WORLD, "world", key, value, importance=importance)

    def _find(self, scope, agent, key):
        return (
            self.db.query(Memory).filter(
                Memory.world_id == self.world.id,
                Memory.agent == agent,
                Memory.scope == scope,
                Memory.key == key,
            ).first()
        )

    # ---------------- 检索 ----------------
    def recall(self, agent: str, scope: MemoryScope = None, key_prefix: str = None,
               top_k: int = 10, include_dormant: bool = False):
        """返回按检索权重降序的记忆列表；召回即视为访问（强化记忆）。"""
        q = self.db.query(Memory).filter(
            Memory.world_id == self.world.id, Memory.agent == agent)
        if scope is not None:
            q = q.filter(Memory.scope == scope)
        if key_prefix:
            q = q.filter(Memory.key.like(f"{key_prefix}%"))
        if not include_dormant:
            q = q.filter(or_(Memory.scope == MemoryScope.WORLD,
                             Memory.is_dormant.is_(False)))
        rows = q.all()
        cur = self.current_tick
        scored = [(self.retrieval_weight(m, cur), m) for m in rows]
        scored.sort(key=lambda x: x[0], reverse=True)
        result = [m for _, m in scored[:top_k]]
        for m in result:
            m.access_count = (m.access_count or 0) + 1
            m.last_accessed_tick = cur
            m.is_dormant = False
        if result:
            self.db.flush()
        return result

    def recall_one(self, agent: str, scope: MemoryScope, key: str):
        """精确取一条；命中即视为访问，休眠记忆被强线索唤回。"""
        m = self._find(scope, agent, key)
        if m is None:
            return None
        if m.is_dormant and m.scope != MemoryScope.WORLD:
            m.is_dormant = False
        m.access_count = (m.access_count or 0) + 1
        m.last_accessed_tick = self.current_tick
        self.db.flush()
        return m

    def retrieval_weight(self, m: Memory, current_tick: int) -> float:
        """确定性检索权重：世界记忆恒为 1.0。"""
        if m.scope == MemoryScope.WORLD:
            return 1.0
        age = max(0, (current_tick or 0) - (m.last_accessed_tick or 0))
        recency = math.exp(-RECENCY_LAMBDA * age)
        freq = 1.0 + FREQ_FACTOR * math.log1p(m.access_count or 0)
        return float(m.importance or 0.5) * recency * freq

    # ---------------- 巩固 / 清理 / 遗忘 ----------------
    def consolidate(self):
        """把重要度达标的短期记忆提升为长期记忆，并删除原短期行。"""
        cur = self.current_tick
        shorts = (
            self.db.query(Memory).filter(
                Memory.world_id == self.world.id,
                Memory.scope == MemoryScope.SHORT,
            ).all()
        )
        for s in shorts:
            if (s.importance or 0) < CONSOLIDATE_THRESHOLD:
                continue  # 低重要度短期记忆不值得长期保留，留待过期清理
            existing = self._find(MemoryScope.LONG, s.agent, s.key)
            if existing:
                existing.importance = min(
                    1.0, (existing.importance or 0) * 0.6 + (s.importance or 0) * 0.4)
                existing.value = s.value
                existing.access_count = (existing.access_count or 0) + 1
                existing.last_accessed_tick = cur
                existing.is_dormant = False
            else:
                self.db.add(Memory(
                    world_id=self.world.id, agent=s.agent, scope=MemoryScope.LONG,
                    key=s.key, value=s.value, importance=(s.importance or 0.5),
                    access_count=1, last_accessed_tick=cur, is_dormant=False,
                ))
            self.db.delete(s)
        self.db.flush()

    def purge_expired(self):
        """物理删除过期的短期记忆（草稿清理）。返回清理条数。"""
        cur = self.current_tick
        expired = (
            self.db.query(Memory).filter(
                Memory.world_id == self.world.id,
                Memory.scope == MemoryScope.SHORT,
                Memory.expires_tick.isnot(None),
                Memory.expires_tick <= cur,
            ).all()
        )
        for m in expired:
            self.db.delete(m)
        self.db.flush()
        return len(expired)

    def forget_step(self):
        """对长期记忆重算休眠标记（确定性遗忘曲线，不删除，保留历史）。"""
        cur = self.current_tick
        longs = (
            self.db.query(Memory).filter(
                Memory.world_id == self.world.id,
                Memory.scope == MemoryScope.LONG,
            ).all()
        )
        for m in longs:
            m.is_dormant = self.retrieval_weight(m, cur) < DORMANCY_FLOOR
        self.db.flush()


class MemoryAgent:
    """记忆维护 Agent：每个 tick 末尾统一巩固/清理/遗忘（接入 engine）。"""

    def __init__(self, db, world, tick):
        self.db = db
        self.world = world
        self.tick = tick

    def run(self) -> dict:
        store = MemoryStore(self.db, self.world)
        consolidated = 0
        # 计算巩固了多少条（通过前后短期记忆数量差近似；这里直接执行）
        before = self.db.query(Memory).filter(
            Memory.world_id == self.world.id,
            Memory.scope == MemoryScope.SHORT).count()
        store.consolidate()
        after = self.db.query(Memory).filter(
            Memory.world_id == self.world.id,
            Memory.scope == MemoryScope.SHORT).count()
        consolidated = max(0, before - after)
        purged = store.purge_expired()
        store.forget_step()
        return {"consolidated": consolidated, "purged": purged}
