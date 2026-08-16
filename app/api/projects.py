"""作品路由：列出 / 创建 / 融资（含 world_id 过滤与只读锁）。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Path
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world, require_permission
from app.models.world import World
from app.models.project import Project
from app.models.misc import Intervention
from app.models.player import Player
from app.models.enums import InterventionType, ProjectStatus
from app.auth.roles import PERM_PROJECT_INVEST
from app.schemas.project import ProjectCreate, ProjectOut, ProjectFinancingIn

router = APIRouter(prefix="/worlds/{world_id}/projects", tags=["作品"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    return (
        db.query(Project)
        .filter(Project.world_id == world.id)
        .order_by(Project.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("", response_model=ProjectOut, status_code=http_status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    project = Project(
        world_id=world.id,
        type=payload.type,
        title=payload.title,
        status=payload.status,
        quality_metrics=payload.quality_metrics or {},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/financing", response_model=ProjectOut,
             status_code=http_status.HTTP_200_OK)
def finance_project(
    payload: ProjectFinancingIn,
    project_id: int = Path(..., description="作品 ID"),
    world: World = Depends(require_writable_world),
    player: Player = Depends(require_permission(PERM_PROJECT_INVEST)),
    db: Session = Depends(get_db),
):
    """项目融资（投资人 / GM 核心动作），受 project:invest 权限网关约束。

    - 仅 investor / gm 可发起；
    - 留痕到 interventions（user_id = 发起人玩家 id，可审计）；
    - 作品从 concept/approved 阶段自动过渡为 financing；
    - 在 quality_metrics 中累加 financing_total 与 financings 明细（不破坏既有分项）。
    """
    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="amount 必须为正数")
    project = db.query(Project).filter(
        Project.id == project_id, Project.world_id == world.id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 状态推进：尚在早期筹备阶段则进入融资期
    if project.status in (ProjectStatus.CONCEPT, ProjectStatus.APPROVED):
        project.status = ProjectStatus.FINANCING

    # 融资累计（保留原始分项可追溯）
    qm = dict(project.quality_metrics or {})
    total = float(qm.get("financing_total", 0) or 0) + payload.amount
    financings = list(qm.get("financings", []) or [])
    financings.append({
        "amount": payload.amount,
        "investor_name": payload.investor_name,
        "note": payload.note,
        "by_player_id": player.id,
    })
    qm["financing_total"] = total
    qm["financings"] = financings
    project.quality_metrics = qm

    db.add(Intervention(
        world_id=world.id, user_id=str(player.id), target_type="project",
        target_id=project.id, intervention_type=InterventionType.FINANCING,
        field="financing_total", old_value=None,
        new_value={"amount": payload.amount, "investor_name": payload.investor_name,
                   "note": payload.note, "project_title": project.title,
                   "financing_total": total},
        reason=payload.note or "项目融资",
    ))
    db.commit()
    db.refresh(project)
    return project
