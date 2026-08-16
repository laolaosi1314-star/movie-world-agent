"""FastAPI 应用入口。"""
import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    worlds,
    characters,
    projects,
    companies,
    markets,
    festivals,
    awards,
    sim,
    events,
    media,
    news,
    reports,
    memories,
    players,
    crisis,
    commerce,
    romance,
)
from app.llm.client import get_llm_status

app = FastAPI(title="影视世界 Agent API", version="0.1.0")

# ===== 无状态 + 移动端（App/H5）对接基础设施 =====
# 所有业务状态均在数据库（world_id 隔离），服务端不保存会话；每个请求自带 world_id。
# H5 / 跨域浏览器客户端需 CORS；来源由 CORS_ALLOW_ORIGINS 控制（逗号分隔）。
# 未配置时默认放开（本地开发便利）；生产环境务必显式限定白名单。
_cors_origins = os.getenv("CORS_ALLOW_ORIGINS")
if _cors_origins:
    _allow_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
else:
    _allow_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 直接挂载各业务子路由（避免 router 中间层导致的双层嵌套 include 丢失路由）
for _r in (
    worlds.router,
    characters.router,
    projects.router,
    companies.router,
    markets.router,
    festivals.router,
    awards.router,
    sim.router,
    events.router,
    media.router,
    news.router,
    reports.router,
    memories.router,
    players.router,
    crisis.router,
    commerce.router,
    romance.router,
):
    app.include_router(_r)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/llm/status")
def llm_status(force_template: bool = Query(False, description="若为 true 则视为强制模板")):
    """全局 LLM 诊断（不含密钥）。engine=llm|template 表示实际生效的渲染引擎。"""
    return get_llm_status(force_template=force_template)
