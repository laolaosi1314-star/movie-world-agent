"""记忆路由：列出 / 详情 / 创建（上帝写入）/ 巩固触发 / 删除。

所有端点挂在 /worlds/{world_id}/memories 下，遵循多世界隔离与只读锁约定。
记忆是多 Agent 世界的"大脑"：短期草稿、长期沉淀、世界集体知识都在此读写。
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world
from app.models.world import World
from app.models.misc import Memory
from app.models.enums import MemoryScope
from app.sim.memory import MemoryStore, DEFAULT_SHORT_TTL
from app.schemas.memory import MemoryOut, MemoryWrite, MemoryConsolidateResult

router = APIRouter(prefix="/worlds/{world_id}/memories", tags=["记忆"])

VALID_SCOPES = {"short", "long", "world"}


@router.get("", response_model=list[MemoryOut])
def list_memories(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    scope: Optional[str] = Query(None, description="short/long/world"),
    agent: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
    key_prefix: Optional[str] = Query(None),
    include_dormant: bool = False,
    skip: int = 0,
    limit: int = 100,
):
    q = db.query(Memory).filter(Memory.world_id == world.id)
    if scope:
        q = q.filter(Memory.scope == scope)
    if agent:
        q = q.filter(Memory.agent == agent)
    if key:
        q = q.filter(Memory.key == key)
    if key_prefix:
        q = q.filter(Memory.key.like(f"{key_prefix}%"))
    if not include_dormant:
        q = q.filter(or_(Memory.scope == MemoryScope.WORLD, Memory.is_dormant.is_(False)))
    return q.order_by(Memory.id).offset(skip).limit(limit).all()


@router.get("/{memory_id}", response_model=MemoryOut)
def get_memory(
    memory_id: int,
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    m = db.query(Memory).filter(
        Memory.id == memory_id, Memory.world_id == world.id).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return m


@router.post("", response_model=MemoryOut, status_code=http_status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryWrite,
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"scope 必须为 {VALID_SCOPES}")
    scope = MemoryScope(payload.scope)
    # 世界记忆强制 agent="world"，保证语义一致
    agent = "world" if scope == MemoryScope.WORLD else payload.agent
    store = MemoryStore(db, world)
    mem = store.write(
        scope=scope, agent=agent, key=payload.key, value=payload.value,
        importance=payload.importance,
        ttl_ticks=payload.ttl_ticks if scope == MemoryScope.SHORT else None,
        expires_at=payload.expires_at,
    )
    db.commit()
    db.refresh(mem)
    return mem


@router.post("/consolidate", response_model=MemoryConsolidateResult)
def consolidate_memories(
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    """手动触发记忆维护：短期->长期巩固、过期短期清理、长期遗忘曲线重算。"""
    store = MemoryStore(db, world)
    before = db.query(Memory).filter(
        Memory.world_id == world.id, Memory.scope == MemoryScope.SHORT).count()
    store.consolidate()
    after = db.query(Memory).filter(
        Memory.world_id == world.id, Memory.scope == MemoryScope.SHORT).count()
    purged = store.purge_expired()
    store.forget_step()
    db.commit()
    return MemoryConsolidateResult(consolidated=max(0, before - after), purged=purged)


@router.delete("/{memory_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: int,
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    m = db.query(Memory).filter(
        Memory.id == memory_id, Memory.world_id == world.id).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete(m)
    db.commit()
