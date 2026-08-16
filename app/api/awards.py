"""奖项路由：浏览 / 创建奖项与类别、奖季、提名、获奖、成就累计、历届回顾；
支持上帝模式手动设定获奖（可审计）。
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Path
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world, require_permission
from app.models.world import World
from app.models.award import (
    Award, AwardSeason, AwardCategory, Nomination, Winner,
    AwardAchievement, AwardSeasonStat,
)
from app.models.misc import Intervention
from app.models.player import Player
from app.models.enums import InterventionType, AwardType, WorkDomain, CategoryKind
from app.auth.roles import PERM_AWARD_CREATE, PERM_WORLD_INTERVENE, critic_can_create_award
from app.schemas.award import (
    AwardCreate, AwardOut, AwardCategoryCreate, AwardCategoryOut,
    WinnerSet, WinnerOut, NominationOut, AwardAchievementOut, AwardSeasonStatOut,
)

router = APIRouter(prefix="/worlds/{world_id}/awards", tags=["奖项"])


def _parse_enum(enum_cls, value: str, field: str):
    """把字符串请求参数安全转换为枚举；非法值返回 422（无状态、可被 App/H5 直接消费）。"""
    try:
        return enum_cls(value)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid {field}: {value!r} (allowed: {[e.value for e in enum_cls]})",
        )


@router.get("", response_model=list[AwardOut])
def list_awards(world: World = Depends(get_world), db: Session = Depends(get_db)):
    return db.query(Award).filter(Award.world_id == world.id).order_by(Award.id).all()


@router.post("", response_model=AwardOut, status_code=http_status.HTTP_201_CREATED)
def create_award(
    payload: AwardCreate,
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_AWARD_CREATE)),
    db: Session = Depends(get_db),
):
    """创建奖项（奖项闸门）。

    - 需 award:create 权限（critic / gm）；
    - 影评人仅可在其 critic_domains 专长领域内创建（与 §15 多领域正交），越界 403。
    """
    domain = _parse_enum(WorkDomain, payload.domain, "domain")
    if not critic_can_create_award(player.role, player.critic_domains, domain.value):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"角色 {player.role.value} 无权在领域 {domain.value} 创建奖项"
            + (f"（你的专长领域：{player.critic_domains}）" if player.critic_domains else ""),
        )
    award = Award(
        world_id=world.id, name=payload.name, founded_year=payload.founded_year,
        organizer=payload.organizer, positioning=payload.positioning,
        level=payload.level, award_type=_parse_enum(AwardType, payload.award_type, "award_type"),
        domain=domain, rules=payload.rules,
    )
    db.add(award)
    db.commit()
    db.refresh(award)
    return award


@router.post("/{award_id}/categories", response_model=AwardCategoryOut,
             status_code=http_status.HTTP_201_CREATED)
def create_category(
    payload: AwardCategoryCreate,
    award_id: int = Path(..., description="奖项 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_AWARD_CREATE)),
    db: Session = Depends(get_db),
):
    """创建奖项类别（奖项闸门，同样受 critic 领域限定）。"""
    award = db.query(Award).filter(
        Award.id == award_id, Award.world_id == world.id).first()
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")
    domain = _parse_enum(WorkDomain, payload.domain, "domain")
    if not critic_can_create_award(player.role, player.critic_domains, domain.value):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"角色 {player.role.value} 无权在领域 {domain.value} 创建奖项类别"
            + (f"（你的专长领域：{player.critic_domains}）" if player.critic_domains else ""),
        )
    cat = AwardCategory(
        award_id=award_id, name=payload.name,
        award_type=_parse_enum(AwardType, payload.award_type, "award_type"),
        domain=domain,
        kind=_parse_enum(CategoryKind, payload.kind, "kind"),
        rules=payload.rules,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.get("/{award_id}/seasons", response_model=list[dict])
def list_seasons(
    award_id: int = Path(..., description="奖项 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    award = db.query(Award).filter(
        Award.id == award_id, Award.world_id == world.id).first()
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")
    return [
        {"id": s.id, "season_number": s.season_number, "year": s.year, "status": s.status}
        for s in db.query(AwardSeason).filter(AwardSeason.award_id == award_id)
        .order_by(AwardSeason.year).all()
    ]


@router.get("/{award_id}/seasons/{season_id}/nominations", response_model=list[NominationOut])
def list_nominations(
    award_id: int = Path(..., description="奖项 ID"),
    season_id: int = Path(..., description="奖季 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    return db.query(Nomination).filter(Nomination.season_id == season_id).all()


@router.get("/{award_id}/seasons/{season_id}/winners", response_model=list[WinnerOut])
def list_winners(
    award_id: int = Path(..., description="奖项 ID"),
    season_id: int = Path(..., description="奖季 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    return db.query(Winner).filter(Winner.season_id == season_id).all()


@router.get("/{award_id}/seasons/{season_id}/stats", response_model=list[AwardSeasonStatOut])
def list_season_stats(
    award_id: int = Path(..., description="奖项 ID"),
    season_id: int = Path(..., description="奖季 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    return db.query(AwardSeasonStat).filter(AwardSeasonStat.season_id == season_id).all()


@router.get("/{award_id}/achievements", response_model=list[AwardAchievementOut])
def list_achievements(
    award_id: int = Path(..., description="奖项 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    return db.query(AwardAchievement).filter(AwardAchievement.award_id == award_id).all()


@router.get("/{award_id}/ceremony-review", response_model=list[dict])
def ceremony_review(
    award_id: int = Path(..., description="奖项 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    """历届回顾：聚合每届各品类赢家（等价物化视图 v_award_ceremony_review 的查询版）。"""
    award = db.query(Award).filter(
        Award.id == award_id, Award.world_id == world.id).first()
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")
    seasons = db.query(AwardSeason).filter(AwardSeason.award_id == award_id).order_by(AwardSeason.year).all()
    result = []
    for s in seasons:
        winners = db.query(Winner).filter(Winner.season_id == s.id).all()
        result.append({
            "season_number": s.season_number,
            "year": s.year,
            "winners": [
                {"category": w.category_name,
                 "project_id": w.project_id,
                 "character_id": w.character_id,
                 "is_user_override": w.is_user_override}
                for w in winners
            ],
        })
    return result


@router.post("/{award_id}/seasons/{season_id}/winners/override",
             response_model=WinnerOut, status_code=http_status.HTTP_201_CREATED)
def override_winner(
    payload: WinnerSet,
    award_id: int = Path(..., description="奖项 ID"),
    season_id: int = Path(..., description="奖季 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_WORLD_INTERVENE)),
    db: Session = Depends(get_db),
):
    """上帝模式：手动设定某奖季某类别获奖。留痕到 interventions（可审计）。

    干预审计：Intervention.user_id 绑定发起此干预的 GM 玩家 id，
    世界历史不被静默改写，可事后追责/回放。
    """
    winner = Winner(
        season_id=season_id, category_id=payload.category_id,
        category_name=db.query(AwardCategory).filter(AwardCategory.id == payload.category_id).first().name
        if db.query(AwardCategory).filter(AwardCategory.id == payload.category_id).first() else "未知类别",
        project_id=payload.project_id, character_id=payload.character_id,
        is_user_override=True,
    )
    db.add(winner)
    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="winner", target_id=season_id,
        intervention_type=InterventionType.AWARD,
        field="category_id", old_value=None,
        new_value={"category_id": payload.category_id,
                   "project_id": payload.project_id,
                   "character_id": payload.character_id},
        reason=payload.reason or "上帝模式手动设定奖项",
    ))
    db.commit()
    db.refresh(winner)
    return winner
