"""新闻 API：列出新闻、按 ID 重新渲染（测试 LLM 插槽切换 / 上帝模式刷新）。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_world_id, get_world, require_writable_world
from app.models.world import World
from app.models.news import News
from app.models.enums import NewsType, RenderEngine
from app.schemas.news import NewsOut, NewsListOut
from app.llm.client import get_llm_client
from app.sim.media_agent import render_template

router = APIRouter(prefix="/worlds/{world_id}/news", tags=["news"])


@router.get("", response_model=NewsListOut)
def list_news(
    world_id: int = Depends(get_world_id),
    db: Session = Depends(get_db),
    outlet_id: Optional[int] = Query(None),
    news_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    q = db.query(News).filter(News.world_id == world_id)
    if outlet_id is not None:
        q = q.filter(News.outlet_id == outlet_id)
    if news_type is not None:
        try:
            nt = NewsType(news_type)
            q = q.filter(News.news_type == nt)
        except ValueError:
            raise HTTPException(status_code=422, detail="news_type 取值非法")
    rows = q.order_by(News.id.desc()).limit(limit).all()
    return NewsListOut(total=len(rows), items=rows)


@router.post("/{news_id}/rerender", response_model=NewsOut)
def rerender_news(
    news_id: int,
    engine: str = Query("llm", description="template 或 llm"),
    force_template: bool = Query(False, description="为 true 时无视 engine 强制用模板（一键降级）"),
    world: World = Depends(require_writable_world),
    db: Session = Depends(get_db),
):
    """用指定引擎重新渲染某条新闻（验证 LLM 插槽 / 模板降级）。
    仅重渲染文本，不改动 fact_pack（保证事实不变）。"""
    news = (
        db.query(News).filter(News.id == news_id, News.world_id == world.id).first()
    )
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")

    if force_template or engine == "template":
        body = render_template(news.fact_pack, _fake_outlet(news), NewsType(news.news_type))
        used_engine = RenderEngine.TEMPLATE
    elif engine == "llm":
        llm = get_llm_client()
        try:
            text = llm.render_narrative(news.fact_pack, news.outlet_snapshot, news.news_type)
        except Exception:
            text = None
        if text:
            body, used_engine = text, RenderEngine.LLM
        else:
            body = render_template(news.fact_pack, _fake_outlet(news), NewsType(news.news_type))
            used_engine = RenderEngine.TEMPLATE
    else:
        raise HTTPException(status_code=422, detail="engine 仅支持 template/llm")

    news.body = body
    news.render_engine = used_engine
    db.commit()
    db.refresh(news)
    return news


def _fake_outlet(news: News):
    """重新渲染时无需真查 MediaOutlet，用 outlet_snapshot 还原一个轻量对象。"""
    from app.models.media import MediaOutlet
    snap = news.outlet_snapshot or {}
    o = MediaOutlet()
    o.name = snap.get("name", "未知媒体")
    o.stance = snap.get("stance", "neutral")
    o.outlet_type = snap.get("outlet_type", "serious")
    o.credibility = snap.get("credibility", 50)
    return o
