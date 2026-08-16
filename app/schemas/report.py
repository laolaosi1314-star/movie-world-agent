"""报告（月/季/年）Schema。

报告是**聚合计算结果**，不持久化（Phase 4 内由报告聚合器实时计算并返回）。
数字一律来自数据库真实查询，保证与 world/projects/events 等一致（防失真）。
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ReportSection(BaseModel):
    """报告中的一个小节（如"年度票房冠军"）。"""
    key: str
    title: str
    value: Any = None
    detail: Optional[str] = None


class ReportOut(BaseModel):
    """一份聚合报告。data 内含各 section；结构化便于前端直接渲染。"""
    model_config = ConfigDict(from_attributes=True)

    world_id: int
    report_type: str            # monthly/quarterly/annual
    year: int
    quarter: Optional[int] = None
    period_label: str           # 如 "2032年6月" / "2032年Q2" / "2032年度"
    generated_at: datetime
    sections: List[ReportSection]


class ReportSummaryOut(BaseModel):
    world_id: int
    report_type: str
    period_label: str
    generated_at: datetime
    top_line: str               # 一句话摘要，供首页/月报卡片展示
