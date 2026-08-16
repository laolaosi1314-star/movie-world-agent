# 影视世界 Agent — 本地运行与验证指南

> 适用版本：MW + Phase 1（世界/时间/人物/作品）+ Phase 2/3（公司/票房/电影节/奖项）+ Phase 4（媒体/新闻）+ **Phase 5（长期记忆三层）+ Phase 7 之「真实 LLM provider 接入（表达层）」** 已编码。
> 目标：在本地配置 PostgreSQL → 跑 Alembic 迁移 → 用 Uvicorn 启动 → 快速跑通「创建世界 → 人物 → 作品 → 推进时间 → 看事件 → 看记忆 → 看 LLM 渲染（可一键降级）」第一个闭环。

---

## 0. 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | ≥ 3.11（推荐 3.13） | 已用 3.13.12 验证 |
| PostgreSQL | ≥ 14（推荐 16） | 任意本地/容器实例 |
| pip 包 | 见 `requirements.txt` | fastapi / uvicorn / sqlalchemy / alembic / psycopg2-binary / pydantic / httpx |

> LLM 配置（`.env` 中的 `LLM_*`）由 `app/llm/client.py` **内置极简解析器**读取，无需 `python-dotenv`；
> 但 `DATABASE_URL` 仍需由 shell 先 `export`（Alembic 读系统环境变量）。

> Windows 用户默认使用 **Git Bash**（本工程命令均按 bash 语法）。cmd/PowerShell 仅需把 `export` 换成 `set` 或 `$env:`。

---

## 1. 配置 PostgreSQL 数据库连接

### 1.1 创建数据库（任选一种）

**方式 A：本地已装 Postgres（psql）**
```bash
psql -U postgres -c "CREATE DATABASE movie_world;"
```

**方式 B：Docker 一键起**
```bash
docker run -d --name mwpg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 postgres:16
# 容器就绪后：
docker exec -it mwpg psql -U postgres -c "CREATE DATABASE movie_world;"
```

### 1.2 设置连接串（关键）

应用与 Alembic 都从环境变量 **`DATABASE_URL`** 读取连接串（PostgreSQL 默认库名 `movie_world`）。

```bash
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/movie_world"
```

> 也可把上面这行写进工程根目录的 `.env` 文件（项目已依赖 `python-dotenv`）。注意：Alembic 的 `env.py` 直接读系统环境变量，`.env` 需由 shell 先 `source` 或 `set -a; source .env; set +a` 加载。

连接串格式：`postgresql+psycopg2://<user>:<password>@<host>:<port>/<dbname>`

---

## 2. 安装 Python 依赖

```bash
cd movie_world_agent
python -m venv .venv
source .venv/Scripts/activate        # Windows-GitBash；Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

> 若用本机已存在的虚拟环境（如本会话隔离 venv），直接 `pip install -r requirements.txt` 即可，无需重建。

---

## 3. 执行 Alembic 迁移（建表）

确保上一步的 `DATABASE_URL` 仍然在当前 shell 生效，然后：

```bash
# 初始化 Alembic（仅在首次/想重建版本链时需要，已自带 alembic.ini，可跳过）
# alembic init alembic   # ← 本工程已包含 alembic/ 目录，不要重复执行

alembic upgrade head
```

预期输出类似：
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, MW + Phase1 ...
INFO  [alembic.runtime.migration] Running upgrade 0001_initial -> 0002_phase2_phase3, ...
INFO  [alembic.runtime.migration] Running upgrade 0002_phase2_phase3 -> <...>, ...
```

此时数据库会建立全部 28 张表（world / characters / projects / companies / festivals / award_* / events / media_outlets / news / memories …）。Phase 5 的 `0004_phase5` 会在 `memories` 表上扩展衰减相关字段（不新增表）。

常用维护命令：
```bash
alembic current          # 查看当前迁移版本
alembic history          # 查看迁移链
alembic downgrade -1     # 回退一个版本（谨慎）
```

---

## 4. 启动服务（Uvicorn）

```bash
# 已在 .venv 激活且 DATABASE_URL 已 export 的前提下
cd movie_world_agent
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后你会看到：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

快速探活：
```bash
curl http://localhost:8000/health
# => {"status":"ok"}
```

交互式文档（自动生成）：
- Swagger UI： http://localhost:8000/docs
- ReDoc： http://localhost:8000/redoc

---

## 5. 跑通第一个闭环（核心验证）

下面用 **curl** 与 **Python 脚本** 两种形式演示同一条链路：
**创建世界 → 创建人物 → 创建作品 → 推进时间 → 查看事件**。

### 5.1 curl 版本（逐步，方便观察每个返回值）

```bash
BASE="http://localhost:8000"

# (1) 创建世界（存档）。记下返回的 id，下面用 WID 代替
WID=$(curl -s -X POST "$BASE/worlds" \
  -H 'Content-Type: application/json' \
  -d '{"name":"测试世界A","description":"本地联调用的小世界"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "新世界 ID = $WID"

# (2) 创建人物（演员）
curl -s -X POST "$BASE/worlds/$WID/characters" \
  -H 'Content-Type: application/json' \
  -d '{"type":"actor","name":"林夏","birth_year":2000,"nationality":"中国","career_stage":"debut","attributes":{"演技":80,"人气":60}}' \
  | python -m json.tool

# (3) 创建作品（电影），状态 concept 表示刚有创意
curl -s -X POST "$BASE/worlds/$WID/projects" \
  -H 'Content-Type: application/json' \
  -d '{"type":"film","title":"星河彼端","status":"concept","quality_metrics":{"剧本":90,"导演":85,"表演":88}}' \
  | python -m json.tool

# (4) 推进时间 1 个月（Tick）。引擎会推进作品生命周期、演化人物属性，并写事件
curl -s -X POST "$BASE/worlds/$WID/sim/advance" \
  -H 'Content-Type: application/json' \
  -d '{"unit":"month"}' \
  | python -m json.tool

# (5) 查看该世界事件流（最新的在最前）
curl -s "$BASE/worlds/$WID/events?limit=20" | python -m json.tool
```

### 5.2 Python 一键冒烟脚本（推荐）

工程已附带 `run_smoke_test.py`（纯标准库 `urllib`，**无需额外依赖**）。启动服务后另开一个终端：

```bash
cd movie_world_agent
python run_smoke_test.py
```

脚本会自动完成上面的 (1)–(5) 并打印每一步结果；最后断言：
- 世界创建成功且初始时间默认为 `2032-06`；
- 至少 1 个人物、1 个作品已落库；
- Tick 之后世界时间推进到 `2032-07`；
- 事件流非空（至少包含「时间推进」事件）；
- **（Phase 5）记忆系统已产生记忆**，且上帝模式写入的世界记忆可被检索、记忆巩固端点可用。

> 离线（不连库）还可直接跑：`python verify_imports.py`（校验路由/表/字段）与
> `python test_phase5_memory.py`（校验确定性衰减与检索权重逻辑）。两者均已全绿。

---

## 6. 多世界 / 只读存档 快速验证（扩展能力）

```bash
BASE="http://localhost:8000"

# 列出所有存档
curl -s "$BASE/worlds" | python -m json.tool

# 把某世界转为只读存档（之后任何写操作应返回 423 Locked）
curl -s -X POST "$BASE/worlds/$WID/archive" | python -m json.tool

# 验证只读锁：对 archived 世界创建人物 → 期望 423
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE/worlds/$WID/characters" \
  -H 'Content-Type: application/json' \
  -d '{"type":"actor","name":"不应被创建"}'

# 基于旧档克隆出一个新可写档（当前版本仅复制世界元信息，实体深拷贝见 BLUEPRINT 返工点）
curl -s -X POST "$BASE/worlds/$WID/clone" | python -m json.tool
```

---

## 6.5 Phase 5 长期记忆系统验证

`memories` 接口全部挂在 `/worlds/{world_id}/memories` 下，遵循多世界隔离与只读锁（archived 世界写操作返回 423）。

```bash
BASE="http://localhost:8000"
# 列出某世界的全部记忆（可加 ?scope=long&agent=character_agent&include_dormant=true 过滤）
curl -s "$BASE/worlds/$WID/memories" | python -m json.tool

# 上帝模式写入一条"世界记忆"（scope=world 时 agent 被强制为 world）
curl -s -X POST "$BASE/worlds/$WID/memories" \
  -H 'Content-Type: application/json' \
  -d '{"agent":"world","scope":"world","key":"industry_climate",
       "value":{"heat_trend":1},"importance":0.9}' | python -m json.tool

# 写入一条"短期记忆"，演示其随后被巩固/过期
curl -s -X POST "$BASE/worlds/$WID/memories" \
  -H 'Content-Type: application/json' \
  -d '{"agent":"character_agent","scope":"short","key":"char:1:tick_heat",
       "value":{"heat":73},"importance":0.4,"ttl_ticks":3}' | python -m json.tool

# 手动触发记忆维护：短期->长期巩固 / 过期短期清理 / 长期遗忘曲线重算
curl -s -X POST "$BASE/worlds/$WID/memories/consolidate" | python -m json.tool
# => {"consolidated": <n>, "purged": <m>}

# 删除某条记忆（上帝模式）
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE "$BASE/worlds/$WID/memories/<memory_id>"
```

记忆如何在世界演化中"活起来"（端到端）：
1. 每推进一个 tick，`character_agent` 读取"世界记忆(行业气候)"与"自身长期记忆(人气动量/奖项荣誉)"作为决策偏置，并把本 tick 的人气快照写成短期草稿；
2. `award_agent` 颁奖时写"荣誉记忆"(`char:{id}:honor`)，下一 tick 被 `character_agent` 读为长尾人气；
3. `media_agent` 生成新闻时召回相关记忆，作为"（背景：…）"注脚注入 `fact_pack`（仅表达层）；
4. tick 末尾 `MemoryAgent` 统一执行 巩固 → 过期清理 → 遗忘，使记忆状态自洽。

---

## 6.7 Phase 7 接入真实 LLM provider（表达层，一键降级）

新闻正文默认由规则模板生成；启用真实大模型后，由它把已确定的 `fact_pack` 渲染成更有可读性的稿件。
**模型只做表达层，不参与任何判定**（谁获奖/谁走红由确定性规则决定），且**不可用时自动降级模板**，世界演化不受影响。

### 6.7.1 配置（整份 `.env`，不要提交真实密钥）

```bash
# 复制模板并按需修改
cp .env.example .env
```

`.env` 关键项（仅 `LLM_*` 会被 app 自动读取）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `LLM_ENABLED` | `false` | 是否启用真实 LLM |
| `LLM_FORCE_TEMPLATE` | `false` | 强制模板（一键降级开关，调试用） |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | 任意 OpenAI 兼容接口前缀 |
| `LLM_API_KEY` | 空 | 密钥（写在 `.env`，不提交） |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名 |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` / `LLM_TOP_P` | `0.7`/`300`/`0.9` | 生成参数 |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | `20`/`1` | 超时秒；仅 5xx 重试 |

兼容端点示例：`DeepSeek=https://api.deepseek.com/v1`、`Moonshot=https://api.moonshot.cn/v1`、
`智谱=https://open.bigmodel.cn/api/paas/v4`、`本地 vLLM=http://localhost:8000/v1`、`Ollama=http://localhost:11434/v1`。

### 6.7.2 验证开关与渲染

```bash
BASE="http://localhost:8000"

# 当前生效引擎（全局，无 world_id，不返回密钥）
curl -s "$BASE/llm/status" | python -m json.tool
# => {"enabled": true, "provider": "openai", "model": "gpt-4o-mini",
#     "base_url": "...", "engine": "llm", "note": "..."}

# 让引擎用真实 LLM 跑一轮 Tick，新闻的 render_engine 记为 llm
# （把 .env 中 LLM_ENABLED=true + 填好密钥，重启 uvicorn 后：）
curl -s -X POST "$BASE/worlds/$WID/sim/advance" -H 'Content-Type: application/json' -d '{"unit":"month"}'
curl -s "$BASE/worlds/$WID/news?limit=5" | python -m json.tool   # 看 render_engine 字段

# 用指定引擎重渲染某条新闻（仅重渲染文本，不改 fact_pack，事实不变）
curl -s -X POST "$BASE/worlds/$WID/news/<news_id>/rerender?engine=llm" | python -m json.tool
curl -s -X POST "$BASE/worlds/$WID/news/<news_id>/rerender?force_template=true" | python -m json.tool
```

### 6.7.3 一键降级（关键容错）

满足任一即全程模板、零网络请求：
- `LLM_ENABLED=false`（默认）；或
- `LLM_FORCE_TEMPLATE=true`；或
- `get_llm_client(force_template=True)`；或
- 网络/鉴权/解析任一失败 → `render_narrative` 返回 `None` → 调用方降级模板。

离线验证（不连库）可跑：`python test_phase7_llm.py`（禁用降级 / 提示词合规 / `_post` 失败降级 / `.env` 读取 / `force_template` 全绿）。

---

## 6.8 负面奖项（金酸梅式）与"尖锐话题"验证

> 前置（Phase 6 之前）。引入正/负奖项区分：负奖基于低分 + 烂口碑自动评选"最差"，
> 其结果直接成为媒体 Agent 的"尖锐话题"，生成充满争议的新闻通稿（详见 BLUEPRINT §14）。

### 6.8.1 自动播种（开箱即用）
新世界首次跨年触发奖季时，若没有任何奖项，引擎会自动播种：
- **金屏奖**（正奖，`award_type=positive`）：最佳影片/导演/男女演员/编剧；
- **金酸梅奖**（负奖，`award_type=negative`）：最差影片/导演/男女演员/编剧。

无需手动建表即可看到正/负两套奖项的评选与报道。

### 6.8.2 手动创建负奖（curl）
```bash
# 创建负奖
curl -X POST "http://localhost:8000/worlds/$WID/awards" \
  -H "Content-Type: application/json" \
  -d '{"name":"金酸梅奖","award_type":"negative","positioning":"年度吐槽"}'

# 为负奖添加类别（award_id 取上一步返回值）
curl -X POST "http://localhost:8000/worlds/$WID/awards/$AWID/categories" \
  -H "Content-Type: application/json" \
  -d '{"name":"最差影片","award_type":"negative"}'
```

### 6.8.3 端到端观察（争议通稿）
1. 准备若干"烂片"：低 `composite_quality`、低 `audience_score` 且口碑"高开低走"；
2. 推进时间跨过年边界（如 `unit=year`），触发奖季评选；
3. 查看新闻：
   ```bash
   curl "http://localhost:8000/worlds/$WID/news" | python -m json.tool
   ```
4. 应能看到 `news_type=controversy` 的报道：
   - **即时争议**：负奖颁奖事件（`category=负面奖项`）被分类为争议，由八卦/毒舌媒体产出；
   - **后续争议（尖锐话题）**：同一负奖结果写入世界记忆 `sharp_topics`，在**下一 tick** 由媒体再次生成争议通稿。
5. 查看尖锐话题记忆（world 作用域，key=`sharp_topics`）：
   ```bash
   curl "http://localhost:8000/worlds/$WID/memories?scope=world&key=sharp_topics" | python -m json.tool
   ```

### 6.8.4 离线单测
不连库可跑：`python test_negative_awards.py`（枚举取值 / 负面判定单调性 / 高开低走惩罚 / 分类路由 / 尖锐 fact_pack 与媒体挑选，全绿）。

---

## 6.9 多领域 / 跨界奖项（电视·音乐）验证（Phase 3.x）

> 在 §15 三维正交架构（domain × award_type × kind）下，奖项体系已支持电视（视帝/视后/最佳剧集）与音乐（最佳专辑/单曲/男女歌手/作词作曲），并可单奖项跨界（金屏奖=电影类+电视类+音乐类）。
> 负奖跨领域同样走 §14 的 sharp_topics→争议通稿闭环（domain 无关）。

### 6.9.1 自动播种（开箱即用）
新世界首次跨年触发奖季时，若没有任何奖项，引擎自动播种三大领域正/负奖：
- **金屏奖**（film 正）：最佳影片/导演/男女演员/编剧；
- **金酸梅奖**（film 负）：最差影片/导演/男女演员/编剧；
- **金屏剧奖**（tv 正）：最佳剧集/导演(剧集)/男女主角/编剧(剧集)；
- **金唱片奖**（music 正）：最佳专辑/单曲/男女歌手/作词/作曲；
- **金酸梅剧奖**（tv 负）：最差剧集/导演(剧集)/男女主角/编剧(剧集)；
- **金扫帚奖**（music 负）：最差专辑/单曲/男女歌手/作词/作曲。

### 6.9.2 手动创建电视/音乐奖项（curl）
```bash
# 创建电视正奖（domain=tv）
curl -X POST "http://localhost:8000/worlds/$WID/awards" \
  -H "Content-Type: application/json" \
  -d '{"name":"金屏剧奖","award_type":"positive","domain":"tv","positioning":"年度剧集表彰"}'

# 为该奖项添加"最佳男主角"类别（kind=actor_male）
curl -X POST "http://localhost:8000/worlds/$WID/awards/$AWID/categories" \
  -H "Content-Type: application/json" \
  -d '{"name":"最佳男主角","award_type":"positive","domain":"tv","kind":"actor_male"}'

# 创建音乐负奖（domain=music）
curl -X POST "http://localhost:8000/worlds/$WID/awards" \
  -H "Content-Type: application/json" \
  -d '{"name":"金扫帚奖","award_type":"negative","domain":"music","positioning":"年度音乐吐槽"}'
# 非法 domain/kind 返回 422（便于 App/H5 直接消费错误）
```

### 6.9.3 端到端观察（跨领域分布 + 争议通稿）
1. 创建若干电视/音乐作品（type=tv / album / single）并推进到 `released`；
2. 跨年触发奖季：`curl -X POST "$BASE/worlds/$WID/sim/advance" -d '{"unit":"year"}'`；
3. 查看某奖项的获奖分布（含领域/类别）：
   ```bash
   curl "$BASE/worlds/$WID/awards/$AWID/seasons/$SID/winners" | python -m json.tool
   ```
4. 音乐/电视烂作（低 composite_quality、低口碑）会被金扫帚奖/金酸梅剧奖评为"最差"，
   其颁奖事件 `category=负面奖项`，并被写入世界记忆 `sharp_topics`（带 `domain` 元数据），
   在**下一 tick** 由媒体 Agent 生成争议通稿（`news_type=controversy`）。
5. 校验 sharp_topics 含跨领域条目：
   ```bash
   curl "$BASE/worlds/$WID/memories?scope=world&key=sharp_topics" | python -m json.tool
   ```

### 6.9.4 离线单测
不连库可跑：
- `python test_multidomain_awards.py`（枚举 / CATEGORY_DEFS 覆盖 / 默认奖项三领域 / domain 过滤 / `_pick` 歌手·专辑·单曲·作词·作曲路由 / 跨领域 `_badness` 一致性，全绿）；
- `python verify_imports.py`（新增 `award_domain_col`/`category_domain_col`/`category_kind_col`/`work_domain_enum_values`/`project_type_has_music` 等校验全 `True`）；
- `python test_negative_awards.py`（既有负奖回归仍全绿）。

### 6.9.5 移动端（App/H5）对接前置
- 所有接口**无状态**：世界状态全部存库（world_id 隔离），服务端不保存会话；每个请求自带 `world_id`（路径参数），请求级 DB 会话（依赖注入），无 Cookie/Session；
- H5 跨域需 CORS：启动前 `export CORS_ALLOW_ORIGINS="https://your-h5.example.com"`（逗号分隔；留空则本地开发放开 `*`）；
- 错误码语义：`423 Locked`=只读存档不可写、`422`=参数校验失败（含非法 domain/kind）、`404`=资源不存在；
- 完整契约与字段规范见 `API_CONTRACT.md`。

### 6.10 用户角色体系（Phase 6）验证

> 迁移与启动：`alembic upgrade head`（含 `0007_player_roles`）→ `uvicorn app.main:app --reload`。
> 全部接口挂在 `/worlds/{world_id}/players` 命名空间，玩家身份由 `Authorization: Bearer <player_key>` 解析。

**1) 创建玩家（GET/POST 形态）**
```bash
# 观众
curl -X POST "http://localhost:8000/worlds/1/players" \
  -H "Content-Type: application/json" \
  -d '{"name":"小明","role":"audience"}'
# 影评人（须指定 critic_domains，否则 422）
curl -X POST "http://localhost:8000/worlds/1/players" \
  -H "Content-Type: application/json" \
  -d '{"name":"影评老张","role":"critic","critic_domains":["film","tv"]}'
# 投资人
curl -X POST "http://localhost:8000/worlds/1/players" \
  -H "Content-Type: application/json" \
  -d '{"name":"王总","role":"investor"}'
# GM（世界中首个 GM 可自举；其后须既有 GM 令牌，否则 403）
curl -X POST "http://localhost:8000/worlds/1/players" \
  -H "Content-Type: application/json" \
  -d '{"name":"造物主","role":"gm"}'
```
响应含一次性下发的 `player_key`（64 位十六进制），客户端自行保存。

**2) 身份校验（Bearer）**
```bash
# 携带令牌查询自身身份
curl "http://localhost:8000/worlds/1/players/me" \
  -H "Authorization: Bearer <player_key>"
# 无令牌 → 401；跨 world_id 令牌 → 401；停用令牌 → 401
```

**3) 角色边界（无状态、请求级）**
- 观众调用 `POST .../players/{id}/deactivate` → `403`（仅 GM 的 `player:admin` 可）；
- GM 调用同上 → 成功；只读存档上的写操作 → `423`；
- 影评人创建音乐类奖项但 `critic_domains=["film"]` → 由 `critic_can_create_award()` 拒绝（业务层 422/403）。

**4) 离线单测与校验（不连库）**
```bash
python verify_imports.py        # player_table_cols / player_role_enum_values / gm_is_superset /
                                # audience_no_intervene / critic_domain_* / write_perms_has_intervene 全 True
python test_phase6_identity.py  # 枚举/模型列/权限矩阵边界/影评人领域限定/_resolve_player/require_permission(401/403/423) 全绿
```

### 6.11 Phase 6（二）业务动作绑定 + 玩家视角（端到端，需本地 PG）

> 前置：`alembic upgrade head`（含 0007_player_roles、0008_intervention_financing）→ `uvicorn` 启动。
> 假设 world_id=1，已用 GM 令牌 `<GM_KEY>`、投资人令牌 `<INV_KEY>`、观众令牌 `<AUD_KEY>`。

**1) 推进时间（任何角色可，只读存档 423）**
```bash
curl -X POST "http://localhost:8000/worlds/1/sim/advance" -H "Authorization: Bearer <AUD_KEY>" \
  -H "Content-Type: application/json" -d '{"unit":"month"}'   # 200
curl -X POST "http://localhost:8000/worlds/1/sim/advance"                     # 无令牌 → 401
```

**2) 项目融资（仅 investor/gm，留痕 Intervention(FINANCING)）**
```bash
curl -X POST "http://localhost:8000/worlds/1/projects/10/financing" \
  -H "Authorization: Bearer <INV_KEY>" -H "Content-Type: application/json" \
  -d '{"amount":1.2,"investor_name":"星海影业","note":"A轮"}'      # 200；状态迁 financing
curl -X POST "http://localhost:8000/worlds/1/projects/10/financing" \
  -H "Authorization: Bearer <AUD_KEY>" -H "Content-Type: application/json" \
  -d '{"amount":1.0}'                                              # 403（观众无权 project:invest）
```

**3) 奖项闸门（critic 领域限定）**
```bash
# 影评人 critic_domains=["film"] 创建音乐奖 → 403
curl -X POST "http://localhost:8000/worlds/1/awards" -H "Authorization: Bearer <CRITIC_FILM_KEY>" \
  -H "Content-Type: application/json" -d '{"name":"金唱片奖","domain":"music","award_type":"positive"}'  # 403
```

**4) 上帝干预审计（user_id 归因）**
```bash
curl -X POST "http://localhost:8000/worlds/1/awards/2/seasons/3/winners/override" \
  -H "Authorization: Bearer <GM_KEY>" -H "Content-Type: application/json" \
  -d '{"category_id":5,"project_id":10,"character_id":7,"reason":"手动颁奖"}'   # 200
# 查库：interventions.user_id = 该 GM 的 player.id（不再是无意义的 'god'）
```

**5) 玩家视角 / 能力接口（App/H5 首页聚合）**
```bash
curl "http://localhost:8000/worlds/1/players/me" -H "Authorization: Bearer <INV_KEY>"
# → PlayerMeOut：含 capabilities + actions（投资人可见 project:invest 动作）
curl "http://localhost:8000/worlds/1/players/me/portal" -H "Authorization: Bearer <INV_KEY>"
# → PlayerPortalOut：player + world 快照 + recent_events（单次获取首页全部数据）
```

**6) 离线单测与校验（不连库）**
```bash
python verify_imports.py        # 新增 action_catalog_nonempty / gm_sees_all_actions /
                                # player_me_out_import / financing_enum_value /
                                # project_invest_is_write_perm / player_admin_not_world_write 全 True
python test_phase6_actions.py   # 动作目录/四动作网关(401·403·423)/PlayerMeOut·Portal 装配/融资枚举 全绿
                                # 与既有 test_phase6_identity 等合计 52 项单测全绿
```

---

## 6.12 舆论与危机公关（§17.3，需本地 PG）

> 前置：`alembic upgrade head`（含 `0009_scandal_crisis`）→ `uvicorn` 启动；world_id=1，
> 人物 character_id=7（假设存在），GM 令牌 `<GM_KEY>`。
> 全程与 §14「负面奖项 → sharp_topics → 媒体争议通稿」闭环复用，媒体 Agent 无需改动。

**1) 黑料爆料（crisis:manage 网关；观众令牌 → 403）**
```bash
POST /worlds/1/scandals  -H "Authorization: Bearer <GM_KEY>"
  {"character_id":7,"scandal_type":"affair","title":"某明星出轨","severity":8,
   "evidence_strength":7,"is_confirmed":true,"exposed":true}
# → 201；stage=spreading；留痕 Intervention(scandal)
curl -X POST "http://localhost:8000/worlds/1/scandals" -H "Authorization: Bearer <AUD_KEY>" \
  -H "Content-Type: application/json" -d '{"character_id":7,"title":"x"}'   # 403（观众无 crisis:manage）
```

**2) 推进 tick 触发丑闻演化 → 复用 §14 媒体闭环**
```bash
curl -X POST "http://localhost:8000/worlds/1/sim/advance" -H "Authorization: Bearer <GM_KEY>" \
  -H "Content-Type: application/json" -d '{"unit":"quarter"}'   # ≥2 tick 后 SPREADING→ERUPTED
# 观察：
#  - events 出现「丑闻争议」类别（major），媒体 Agent 当 tick 生成 CONTROVERSY 新闻；
#  - world 记忆 sharp_topics 被写入（domain="crisis"），下一 tick 媒体自动生成争议通稿；
#  - 该人物 char:{id}:notorious 长期记忆写入 → 后续报道背景注脚带出"曾因丑闻塌房"。
```

**3) 多阶段公关（确定性恢复曲线，留痕 Intervention(crisis_pr)）**
```bash
# 实锤出轨 → 选「公开道歉」加分；若误选「反向营销/洗白」则遭群嘲加速塌房
curl -X POST "http://localhost:8000/worlds/1/scandals/1/pr" -H "Authorization: Bearer <GM_KEY>" \
  -H "Content-Type: application/json" -d '{"strategy":"apology","note":"公开致歉"}'
# → 201 CrisisPROut：impact={delta_heat,delta_opinion,note}；scandal 转入 resolving
curl "http://localhost:8000/worlds/1/scandals/1/pr"   # GET 公关历史
```

**4) 埋点自检（离线，不连库）**
```bash
python test_phase17_crisis.py   # 枚举/权限矩阵/evaluate_pr 胜负手矩阵/状态机演化/
                                # sharp_topics 复用/_badness 桥接 共 16 项全绿
                                # 全局 68 项单测全绿
```

**5) 只读存档保护**
```bash
curl -X POST "http://localhost:8000/worlds/1/scandals" -H "Authorization: Bearer <GM_KEY>" ...
# 若 world 状态=archived → 423 Locked（crisis:manage 属写类权限）
```

---

## 6.13 商业时尚与塌房违约金（§17.1，需本地 PG）

> 前置：`alembic upgrade head`（含 `0010_commercial`）→ `uvicorn` 启动；world_id=1，人物
> character_id=7（假设存在、高热度），GM 令牌 `<GM_KEY>`。
> **本模块与 §17.3 塌房强耦合**：丑闻塌房（COLLAPSED）瞬间自动触发违约金结算，媒体 Agent 零改动。

**1) GM 签约代言 / 安排封面（commerce:manage 网关；观众令牌 → 403）**
```bash
POST /worlds/1/commerce/endorsements  -H "Authorization: Bearer <GM_KEY>"
  {"character_id":7,"brand_name":"Lumière 顶奢","tier":"top_luxury","annual_fee":1200,
   "penalty_rate":0.8,"has_morals_clause":true,"duration_ticks":12}
# → 201；status=active；留痕 Intervention(CREATE)
POST /worlds/1/commerce/covers  -H "Authorization: Bearer <GM_KEY>"
  {"character_id":7,"magazine_name":"VOGUE 风尚","tier":"top5","issue_tick":6}
# → 201；status=active
```

**2) 塌房触发违约金（§17.3 桥接，系统自动）**
```bash
# 先确保该人物有带道德条款的生效代言（见上）；再用 §6.12 方式引爆并选择错误公关使其塌房
POST /worlds/1/scandals  -H "Authorization: Bearer <GM_KEY>"
  {"character_id":7,"scandal_type":"drugs","title":"某艺人吸毒","severity":9,
   "evidence_strength":9,"is_confirmed":true,"exposed":true}
curl -X POST "http://localhost:8000/worlds/1/sim/advance" -H "Authorization: Bearer <GM_KEY>" \
  -H "Content-Type: application/json" -d '{"unit":"quarter"}'   # 演化至 COLLAPSED
# 观察：
#  - endorsements 该人物名下合约 → status=breached，penalty_amount = 年代言费×比例×剩余年限；
#  - characters.commercial_value 重挫（severity=9 → 贬值约 87%）；
#  - 未刊登 magazine_covers → status=terminated（取消）；
#  - 事件出现「商业塌房」类别（historic）；sharp_topics 写入 domain=commerce → 媒体下一 tick 生成争议通稿；
#  - 投资人后续可据商业崩塌评估融资回撤。
```

**3) 商业概览 / 解约**
```bash
GET /worlds/1/commerce/characters/7/summary
# → {commercial_value, active_endorsements, breached_endorsements,
#    active_covers, cancelled_covers, total_penalty_paid}
POST /worlds/1/commerce/endorsements/1/terminate  -H "Authorization: Bearer <GM_KEY>"
  {"voluntary":true}   # 协商解约（无违约金）；voluntary=false 标记违约
```

**4) 埋点自检（离线，不连库）**
```bash
python test_phase17_commerce.py   # 枚举/权限矩阵/违约金纯函数/塌房桥接(违约+违约金+贬值+封面取消+sharp_topics)/
                                  # 自动签约确定性(cap 限流·塌房不再接约) 共 9 项全绿
                                  # 全局 77 项单测全绿
```

**5) 只读存档保护**
```bash
curl -X POST "http://localhost:8000/worlds/1/commerce/endorsements" -H "Authorization: Bearer <GM_KEY>" ...
# 若 world 状态=archived → 423 Locked（commerce:manage 属写类权限）
```

---

## 6.14 人际情感网络与人生档案馆（§17.2，需本地 PG）

> 前置：`alembic upgrade head`（含 `0011_relationship`）→ `uvicorn` 启动；world_id=1，
> 人物 character_id=10（歌手/偶像型，高热度）、character_id=11（合作演员）；GM 令牌 `<GM_KEY>`。
> 本模块与 §17.3 强耦合（一方出轨丑闻自动拆散关系），并复用 §14 媒体闭环（媒体 Agent 零改动）。

**0) 一键联调脚本（推荐）** —— `scripts/e2e_demo.sh` 已封装「编排恋情 → 官宣(脱粉/回踩) → 出轨爆料 → 推 tick 至塌房 → 情感拆散 + 代言违约赔付 + 商业价值重挫 → 人生档案馆注脚」完整叙事弧，并自带 Alembic 迁移、uvicorn 自启、jq 解析与进度打印。

```bash
# 1) 准备本地 PG（示例）
createdb movie_world
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/movie_world"
pip install -r requirements.txt        # 含 psycopg2-binary / alembic / uvicorn
# 2) 一键跑通（Git Bash / WSL 中执行）
bash scripts/e2e_demo.sh
# 关键观察点（脚本会逐项打印）：
#   - 官宣后林晚星 commercial_value 由 ≈85 → 随脱粉下滑（镜像贬值）
#   - 丑闻 tick 演化 stage: spreading→erupted→collapsed（severity=9 必然塌房）
#   - 塌房瞬间 breached_endorsements=1、total_penalty_paid>0、commercial_value 重挫至约 13%
#   - 关系 ended_reason="因一方出轨丑闻拆散"
#   - /characters/{id}/archive 的 legacy_footnotes 自动带出"曾因出轨丑闻塌房"
```

**完整叙事联调剧本（手动 curl 等价版）** 见下方 1)~5)；脚本即把这些命令串成可复现流程。

**1) GM 编排恋情 / 官宣 / 生子（relationship:manage 网关；观众令牌 → 403）**
```bash
POST /worlds/1/relationships  -H "Authorization: Bearer <GM_KEY>"
  {"character_a_id":10,"character_b_id":11,"romance_type":"dating","is_public":false}
# → 201；status=active（地下）；留痕 Intervention(CREATE)
POST /worlds/1/relationships/1/reveal  -H "Authorization: Bearer <GM_KEY>" {}   # 官宣公开
# → status 转 is_public=true；即时结算粉丝蝴蝶效应（偶像型 10 脱粉，heat 下滑）；
#   写「情感争议」事件（当 tick CONTROVERSY 新闻）+ sharp_topics(domain=relationship)
POST /worlds/1/relationships/1/add-child  -H "Authorization: Bearer <GM_KEY>" {"count":1}
# → child_count+1；若已公开则触发「新生儿」粉丝反应
curl -X POST "http://localhost:8000/worlds/1/relationships" -H "Authorization: Bearer <AUD_KEY>" \
  -H "Content-Type: application/json" -d '{"character_a_id":10,"character_b_id":11}'   # 403（观众无权）
```

**2) 自然曝光 + 与 §17.3 出轨拆散（系统自动）**
```bash
# 先编排地下恋情（is_public=false, publicness=58），推进 tick：
curl -X POST "http://localhost:8000/worlds/1/sim/advance" -H "Authorization: Bearer <GM_KEY>" \
  -H "Content-Type: application/json" -d '{"unit":"month"}'
# publicness 每 tick +6 → 达 60 阈值自动公开并结算蝴蝶效应
# 再对该人物引爆出轨丑闻（§6.12），演化中 RomanceAgent 检测到 affair 丑闻 → 关系自动 ended
POST /worlds/1/scandals  -H "Authorization: Bearer <GM_KEY>"
  {"character_id":10,"scandal_type":"affair","title":"某顶流出轨","severity":9,
   "evidence_strength":8,"is_confirmed":true,"exposed":true}
# → 关系 ended_reason="因一方出轨丑闻拆散"，出轨方额外脱粉；事件「情感地震」+ sharp_topics
```

**3) 人生档案馆（只读聚合，仅需 world:read）**
```bash
GET /worlds/1/characters/10/archive
# → { name, heat, commercial_value, award_summary, awards[], commercial[], scandals[],
#      relationships[], career_history[], major_events[], timeline[](合并排序时间轴),
#      legacy_footnotes[](读取长期记忆：塌房/商业崩塌/奖项荣誉，随岁月沉淀动态渲染) }
# 同一人物在塌房前后两次查询：legacy_footnotes 会从空 → 自动带出"曾因出轨丑闻塌房"注脚
```

**4) 埋点自检（离线，不连库）**
```bash
python test_phase17_relationship.py   # 枚举/权限矩阵/fan_profile/compute_fan_reaction 胜负手/
                                     # 自然曝光公开结算/出轨拆散/sharp_topics 复用/人生档案馆聚合+注脚 共 12 项全绿
                                     # 全局 89 项单测全绿
```

**5) 只读存档保护**
```bash
curl -X POST "http://localhost:8000/worlds/1/relationships" -H "Authorization: Bearer <GM_KEY>" ...
# 若 world 状态=archived → 423 Locked（relationship:manage 属写类权限）
```

---

---

## 7. 常见问题排查

| 现象 | 原因 / 解决 |
|---|---|
| `ModuleNotFoundError: No module named 'psycopg2'` | `pip install -r requirements.txt` 未执行或 `.venv` 未激活。 |
| `connection refused` / `could not connect to server` | PostgreSQL 未启动，或 `DATABASE_URL` 主机/端口/密码错误。先用 `psql $DATABASE_URL` 验证连通。 |
| Alembic 报 `Target database is not up to date` | 已存在旧表但版本链缺失。确认 `alembic upgrade head` 成功；不要手动 `CREATE TABLE`。 |
| `sqlalchemy.exc.ProgrammingError: permission denied` | 数据库用户无建表权限，换有权限的 role 或 `GRANT`。 |
| 启动时 `DATABASE_URL` 未生效 | Alembic 读**系统环境变量**；确保 `export` 在运行 `alembic`/`uvicorn` 的同一 shell 中。 |
| 写入 archived 世界被拒 | 这是**预期行为**（423 Locked）。需先 `clone` 出新档再写。 |
| Tick 后作品状态未到 `released` | 引擎每 tick 仅推进 1 个生命周期阶段；连续推进（如 `year`）才会走到上映。属正常设计。 |

---

## 8. 下一步

- 想要真实「因果 AI」而非规则占位（`complete` 判定用途）：在遵守 §11 前提下，可在 `LLMClient.complete` 接入模型，但**不得**写入影响世界状态的分支（见 BLUEPRINT 返工点 1）。
- 想要「基于当前设定开新档」的深拷贝：实现 `clone` 的实体级复制（BLUEPRINT 返工点 2）。
- Phase 7 剩余：World Director 冲突校验（多 Agent 写入协调，记忆层已可支撑，不碰判定链）。
- Phase 6（用户角色）、Phase 8（完整 UI）按里程碑继续。Phase 4/5/7(LLM)/负面奖项前置 已完成。

完整架构、表结构与返工点见 `BLUEPRINT.md`。
