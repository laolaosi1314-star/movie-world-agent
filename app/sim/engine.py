"""世界模拟引擎：时间推进（tick）总调度。

一次 advance 流程：
  1. 计算新的年/月与 tick 日期区间；
  2. 创建 SimulationTick 记录（可重放）；
  3. CharacterAgent 驱动人物演化；
  4. ProjectAgent 推进作品生命周期；
  5. 生成"时间推进"事件；
  6. 更新 world 当前时间、tick 计数、updated_at；
  7. 提交事务。
"""
import datetime

from sqlalchemy.orm import Session
from app.models.world import World, SimulationTick
from app.models.event import Event
from app.models.enums import EventLevel
from app.sim.character_agent import CharacterAgent
from app.sim.project_agent import ProjectAgent
from app.sim.company_agent import CompanyAgent
from app.sim.market_agent import MarketAgent
from app.sim.festival_agent import FestivalAgent
from app.sim.award_agent import AwardAgent
from app.sim.media_agent import MediaAgent
from app.sim.crisis_agent import CrisisAgent
from app.sim.commerce_agent import CommercialAgent
from app.sim.romance_agent import RomanceAgent
from app.sim.memory import MemoryAgent

UNIT_MONTHS = {
    "month": 1,
    "quarter": 3,
    "halfyear": 6,
    "year": 12,
}


def advance_world(db: Session, world: World, unit: str) -> SimulationTick:
    if unit not in UNIT_MONTHS:
        raise ValueError(f"invalid unit: {unit}，应为 month/quarter/halfyear/year")

    months = UNIT_MONTHS[unit]
    total_from = world.current_year * 12 + (world.current_month - 1)
    total_to = total_from + months
    to_year = total_to // 12
    to_month = total_to % 12 + 1

    from_date = datetime.datetime(world.current_year, world.current_month, 1, tzinfo=datetime.timezone.utc)
    # 目标月最后一天
    if to_month == 12:
        next_year, next_month = to_year + 1, 1
    else:
        next_year, next_month = to_year, to_month + 1
    to_date = datetime.datetime(next_year, next_month, 1, tzinfo=datetime.timezone.utc) - datetime.timedelta(days=1)

    tick = SimulationTick(
        world_id=world.id,
        tick_index=world.total_ticks + 1,
        unit=unit,
        from_date=from_date,
        to_date=to_date,
        rng_seed_used=world.rng_seed,
    )
    db.add(tick)
    db.flush()

    # 先推进世界时间，使所有 Agent 看到"推进后"的年份（届次/奖季按年份边界触发）
    world.current_year = to_year
    world.current_month = to_month
    world.total_ticks = tick.tick_index
    world.updated_at = datetime.datetime.now(datetime.timezone.utc)

    # 调度各专职 Agent（Phase 1 + Phase 2/3）
    CharacterAgent(db, world, tick).run()
    ProjectAgent(db, world, tick).run()
    CompanyAgent(db, world, tick).run()
    MarketAgent(db, world, tick).run()
    FestivalAgent(db, world, tick).run()
    AwardAgent(db, world, tick).run()
    # §17.3: 危机公关 Agent 演化本世界丑闻，并把话题/事件喂入媒体闭环（位于媒体之前）
    CrisisAgent(db, world, tick).run()
    # §17.2: 情感网络 Agent 演化本世界恋情/绯闻/婚育，并读取 §17.3 出轨丑闻拆散关系（位于媒体之前）
    RomanceAgent(db, world, tick).run()
    # §17.1: 商业 Agent 维护人物商业价值、确定性接洽代言/封面（塌房违约金由 CrisisAgent 触发）
    CommercialAgent(db, world, tick).run()
    # Phase 4: 媒体基于本 tick 事件生成新闻（LLM 仅用于表达层，失败降级模板）
    MediaAgent(db, world, tick).run()
    # Phase 5: 记忆维护（巩固短期->长期、清理过期短期、长期遗忘曲线）
    MemoryAgent(db, world, tick).run()
    # TODO(Phase 7): World Director 冲突校验应在此处统一校验 Agent 写入冲突

    db.add(Event(
        world_id=world.id,
        tick_id=tick.id,
        event_date=to_date.date(),
        level=EventLevel.NORMAL,
        category="时间推进",
        title=f"世界推进至 {to_year}年{to_month}月",
        description=f"本时段（{unit}），影视行业整体{world.industry_status}。",
        causal_chain={"unit": unit, "months": months},
        affected_entities=[{"type": "world", "id": world.id}],
    ))

    db.commit()
    db.refresh(tick)
    return tick
