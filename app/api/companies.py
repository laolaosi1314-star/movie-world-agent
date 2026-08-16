"""公司路由：列出 / 创建（含 world_id 过滤与只读锁）。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Path
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_world, require_writable_world
from app.models.world import World
from app.models.company import Company, CompanyHistory
from app.schemas.company import CompanyCreate, CompanyOut, CompanyHistoryOut

router = APIRouter(prefix="/worlds/{world_id}/companies", tags=["公司"])


@router.get("", response_model=list[CompanyOut])
def list_companies(
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    skip: int = 0, limit: int = 100,
):
    return (
        db.query(Company).filter(Company.world_id == world.id)
        .order_by(Company.id).offset(skip).limit(limit).all()
    )


@router.post("", response_model=CompanyOut, status_code=http_status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    company = Company(
        world_id=world.id,
        name=payload.name,
        type=payload.type,
        founded_year=payload.founded_year,
        country=payload.country,
        style_tag=payload.style_tag,
        capital=payload.capital or 0,
        cash=payload.cash or 0,
        attributes=payload.attributes or {},
    )
    db.add(company)
    db.add(CompanyHistory(
        company_id=company.id, year=world.current_year, month=world.current_month,
        title=f"{company.name} 成立",
        description="公司创立，进入影视行业。",
    ))
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: int = Path(..., description="公司 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(
        Company.id == company_id, Company.world_id == world.id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/{company_id}/history", response_model=list[CompanyHistoryOut])
def company_history(
    company_id: int = Path(..., description="公司 ID"),
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
):
    return (
        db.query(CompanyHistory)
        .join(Company, CompanyHistory.company_id == Company.id)
        .filter(CompanyHistory.company_id == company_id, Company.world_id == world.id)
        .order_by(CompanyHistory.year, CompanyHistory.id).all()
    )
