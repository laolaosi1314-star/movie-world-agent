"""报告 API：月/季/年报聚合查询（只读，数字来自数据库真实查询）。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_world_id, get_world
from app.models.world import World
from app.models.enums import ReportType
from app.schemas.report import ReportOut
from app.sim.media_agent import generate_report

router = APIRouter(prefix="/worlds/{world_id}/reports", tags=["reports"])

VALID = {ReportType.MONTHLY.value, ReportType.QUARTERLY.value, ReportType.ANNUAL.value}


@router.get("/{report_type}", response_model=ReportOut)
def get_report(
    report_type: str,
    world: World = Depends(get_world),
    db: Session = Depends(get_db),
    year: int = Query(..., description="报告年份（世界年）"),
    month: Optional[int] = Query(None, ge=1, le=12),
    quarter: Optional[int] = Query(None, ge=1, le=4),
):
    if report_type not in VALID:
        raise HTTPException(status_code=400, detail="report_type 仅支持 monthly/quarterly/annual")
    if report_type == ReportType.MONTHLY.value and month is None:
        raise HTTPException(status_code=400, detail="月报需提供 month 参数")
    if report_type == ReportType.QUARTERLY.value and quarter is None:
        raise HTTPException(status_code=400, detail="季报需提供 quarter 参数")
    data = generate_report(db, world, report_type, year, month=month, quarter=quarter)
    return ReportOut(**data)
