#!/usr/bin/env bash
# ============================================================================
# 影视世界 Agent —— §17.2（人际情感网络）+ §17.1（商业时尚）+ §17.3（舆论危机）
# 真实端到端联调剧本（本地 PostgreSQL）
#
# 叙事弧：开档 → GM 自举 → 造两位艺人 → 签代言(埋商业价值) →
#         编排地下恋情 → 官宣公开(粉丝蝴蝶效应: 偶像脱粉/回踩) →
#         引爆出轨丑闻 → 推 tick 至塌房(COLLAPSED) →
#         情感关系自动拆散 + 代言违约赔付违约金 + 商业价值重挫 →
#         查「人生档案馆」看岁月沉淀注脚。
#
# 运行环境：Git Bash / WSL / Linux（Windows 用户请用 Git Bash）
# 依赖：bash, curl, jq, Python(venv 含 requirements.txt), 本地 PostgreSQL
#
# 用法：
#   1) 按本地 PG 实情修改下方 DATABASE_URL（或 export 后再运行）。
#   2) 确保已建库：createdb movie_world   （或 psql 执行 CREATE DATABASE）
#   3) bash scripts/e2e_demo.sh
# ============================================================================
set -euo pipefail

# ---------- 0. 配置（按需修改） ----------
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://postgres:postgres@localhost:5432/movie_world}"
PORT=8000
BASE="http://localhost:${PORT}"
PY="${PYTHON:-python}"          # 指向装有依赖的 venv python（如 .venv/bin/python）
START_SERVER="${START_SERVER:-true}"   # 设为 false 可跳过自动起 uvicorn（你已手动起）

# ---------- 工具函数 ----------
api() {                          # api METHOD PATH [JSON] [BEARER_TOKEN]
  local method="$1" path="$2" body="${3:-}" token="${4:-}"
  local args=(-s -X "$method" "$BASE$path" -H "Content-Type: application/json")
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  [ -n "$body"  ] && args+=(-d "$body")
  curl "${args[@]}"
}
jqid()  { echo "$1" | jq -r '.id'; }
jqv()   { echo "$1" | jq -r ".$2"; }

echo "==> 0. 前置检查"
command -v jq  >/dev/null || { echo "✗ 未找到 jq，请先安装: https://stedolan.github.io/jq/"; exit 1; }
command -v "$PY" >/dev/null || { echo "✗ 未找到 python: $PY"; exit 1; }
command -v curl >/dev/null || { echo "✗ 未找到 curl"; exit 1; }

# ---------- 1. 数据库迁移 ----------
echo "==> 1. 执行 Alembic 迁移（含 0011_relationship）"
"$PY" -m alembic upgrade head

# ---------- 2. 启动服务 ----------
if [ "$START_SERVER" = "true" ]; then
  echo "==> 2. 后台启动 uvicorn（PID 将打印；脚本结束仍驻留）"
  nohup "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
    > uvicorn.log 2>&1 &
  UVPID=$!
  echo "    uvicorn PID=$UVPID  (停止: kill $UVPID)"
  # 等待服务可达
  for i in $(seq 1 30); do
    if api GET "/worlds" >/dev/null 2>&1; then echo "    服务已就绪"; break; fi
    sleep 1
  done
else
  echo "==> 2. 跳过启动（START_SERVER=false），假定服务已在 $BASE 运行"
fi

# ---------- 3. 开新档 ----------
echo "==> 3. 开新档"
WRESP=$(api POST "/worlds" '{"name":"端到端联调世界","description":"§17.2 情感×§17.1 商业×§17.3 危机 收官联调"}')
WID=$(jqid "$WRESP")
echo "    world_id=$WID  name=$(jqv "$WRESP" name)"

# ---------- 4. GM 自举 ----------
echo "==> 4. GM 自举（首个 GM 自由创建，一次性下发 player_key）"
PRESP=$(api POST "/worlds/$WID/players" '{"name":"总导演GM","role":"gm"}')
GMKEY=$(echo "$PRESP" | jq -r '.player_key')
echo "    GM player_key=${GMKEY:0:8}...（已省略）"

# ---------- 5. 造两位艺人 ----------
echo "==> 5. 造两位艺人（偶像歌手 × 实力演员）"
C1RESP=$(api POST "/worlds/$WID/characters" \
  "{\"type\":\"singer\",\"name\":\"林晚星\",\"birth_year\":1998,\"career_stage\":\"peak\",\"attributes\":{\"heat\":85,\"idol_appeal\":80}}")
C1=$(jqid "$C1RESP")
echo "    林晚星 id=$C1  heat=$(echo "$C1RESP" | jq -r '.attributes.heat')  idol_appeal=$(echo "$C1RESP" | jq -r '.attributes.idol_appeal')"
C2RESP=$(api POST "/worlds/$WID/characters" \
  "{\"type\":\"actor\",\"name\":\"顾沉\",\"birth_year\":1990,\"career_stage\":\"established\",\"attributes\":{\"heat\":70}}")
C2=$(jqid "$C2RESP")
echo "    顾沉   id=$C2  heat=$(echo "$C2RESP" | jq -r '.attributes.heat')"

# ---------- 6. 签代言（埋下商业价值，供塌房时违约赔付） ----------
echo "==> 6. GM 为林晚星签高奢代言（带道德条款 → 塌房必违约）"
ESIGN=$(api POST "/worlds/$WID/commerce/endorsements" "$GMKEY" \
  "{\"character_id\":$C1,\"tier\":\"high_luxury\",\"brand_name\":\"Aqua 护肤\",\"has_morals_clause\":true,\"duration_ticks\":12}")
EID=$(jqid "$ESIGN")
echo "    代言 id=$EID  品牌=$(jqv "$ESIGN" brand_name)  年费=$(jqv "$ESIGN" annual_fee)万  违约金率=$(jqv "$ESIGN" penalty_rate)"
# 推一 tick，让 CommercialAgent 初始化 commercial_value（≈heat）
api POST "/worlds/$WID/sim/advance" '{"unit":"month"}' "$GMKEY" >/dev/null
SUM0=$(api GET "/worlds/$WID/commerce/characters/$C1/summary")
echo "    林晚星商业价值(官宣前)=$(echo "$SUM0" | jq -r '.commercial_value')"

# ---------- 7. 编排地下恋情 ----------
echo "==> 7. GM 编排地下恋情（is_public=false，随 tick 自然泄露）"
RRESP=$(api POST "/worlds/$WID/relationships" "$GMKEY" \
  "{\"character_a_id\":$C1,\"character_b_id\":$C2,\"romance_type\":\"dating\",\"is_public\":false,\"publicness\":0}")
RID=$(jqid "$RRESP")
echo "    关系 id=$RID  status=$(jqv "$RRESP" status)  is_public=$(jqv "$RRESP" is_public)"

# ---------- 8. 官宣公开（粉丝蝴蝶效应：偶像脱粉/回踩） ----------
echo "==> 8. 官宣公开 → 即时结算粉丝蝴蝶效应（偶像型脱粉 + 回踩）"
api POST "/worlds/$WID/relationships/$RID/reveal" "$GMKEY" '{}' >/dev/null
SUM1=$(api GET "/worlds/$WID/commerce/characters/$C1/summary")
echo "    林晚星官宣后商业价值=$(echo "$SUM1" | jq -r '.commercial_value')（脱粉致人气下滑→商业镜像贬值）"
RELNOW=$(api GET "/worlds/$WID/relationships/$RID")
echo "    关系 is_public=$(echo "$RELNOW" | jq -r '.is_public')  reacted_tick=$(echo "$RELNOW" | jq -r '.reacted_tick')"

# ---------- 9. 引爆出轨丑闻（§17.3，确定性塌房） ----------
echo "==> 9. 对林晚星引爆出轨丑闻（confirmed=true, severity=9）"
SRESP=$(api POST "/worlds/$WID/scandals" "$GMKEY" \
  "{\"character_id\":$C1,\"scandal_type\":\"affair\",\"title\":\"林晚星深夜密会神秘男子\",\"severity\":9,\"evidence_strength\":8,\"is_confirmed\":true,\"exposed\":true}")
SID=$(jqid "$SRESP")
echo "    丑闻 id=$SID  stage=$(jqv "$SRESP" stage)  opinion=$(jqv "$SRESP" public_opinion)"

# ---------- 10. 推进时间直至塌房（COLLAPSED） ----------
echo "==> 10. 推进时间：丑闻演化 → 爆发 → 塌房；同时触发 §17.2 出轨拆散"
for i in $(seq 1 25); do
  api POST "/worlds/$WID/sim/advance" '{"unit":"month"}' "$GMKEY" >/dev/null
  SNOW=$(api GET "/worlds/$WID/scandals/$SID")
  STAGE=$(echo "$SNOW" | jq -r '.stage')
  OP=$(echo "$SNOW" | jq -r '.public_opinion')
  echo "    tick #$i: stage=$STAGE  opinion=$OP"
  [ "$STAGE" = "collapsed" ] && { echo "    ✅ 已塌房（COLLAPSED）"; break; }
done

# ---------- 11. 塌房后果：商业崩塌 ----------
echo "==> 11. 塌房后果：代言违约 + 违约金 + 商业价值重挫"
SUM2=$(api GET "/worlds/$WID/commerce/characters/$C1/summary")
echo "    林晚星商业价值(塌房后)=$(echo "$SUM2" | jq -r '.commercial_value')"
echo "    生效代言=$(echo "$SUM2" | jq -r '.active_endorsements')  违约代言=$(echo "$SUM2" | jq -r '.breached_endorsements')  累计赔付=$(echo "$SUM2" | jq -r '.total_penalty_paid')万"
RELEND=$(api GET "/worlds/$WID/relationships/$RID")
echo "    关系 status=$(echo "$RELEND" | jq -r '.status')  ended_reason=$(echo "$RELEND" | jq -r '.ended_reason')"

# ---------- 12. 人生档案馆（只读聚合 + 岁月沉淀注脚） ----------
echo "==> 12. 查「人生档案馆」GET /characters/$C1/archive"
ARC=$(api GET "/worlds/$WID/characters/$C1/archive")
echo "    姓名=$(echo "$ARC" | jq -r '.name')  类型=$(echo "$ARC" | jq -r '.type')  heat=$(echo "$ARC" | jq -r '.heat')"
echo "    商业价值=$(echo "$ARC" | jq -r '.commercial_value')"
echo "    关系数=$(echo "$ARC" | jq -r '.relationships|length')  丑闻数=$(echo "$ARC" | jq -r '.scandals|length')  时间轴条目=$(echo "$ARC" | jq -r '.timeline|length')"
echo "    legacy_footnotes（岁月沉淀注脚）:"
echo "$ARC" | jq -r '.legacy_footnotes[] | "      - [\(.kind // "note")] \(.label // .text // .)"'

# ---------- 13. 首页聚合（App/H5 对接点） ----------
echo "==> 13. GM 首页聚合 GET /players/me/portal"
PORTAL=$(api GET "/worlds/$WID/players/me/portal" "$GMKEY")
echo "    世界=$(echo "$PORTAL" | jq -r '.world.name')  年份=$(echo "$PORTAL" | jq -r '.world.current_year')  近期事件=$(echo "$PORTAL" | jq -r '.recent_events|length')"
echo "    能力(actions)数=$(echo "$PORTAL" | jq -r '.player.actions|length')  含 relationship:manage=$(echo "$PORTAL" | jq -r '[.player.actions[].permission]|index("relationship:manage")>=0')"

# ---------- 收尾 ----------
echo ""
echo "============================================================"
echo "联调完成 ✅"
echo "  world_id=$WID  GM_KEY 已下发（脚本内）"
echo "  剧本覆盖：编排恋情→官宣(脱粉/回踩)→出轨爆料→塌房(COLLAPSED)"
echo "           → 情感拆散 + 代言违约赔付 + 商业价值重挫 + 人生档案馆注脚"
echo "  uvicorn 仍在后台运行（PID=$UVPID）：可继续手动 curl 体验"
echo "  停止服务: kill $UVPID"
echo "============================================================"
