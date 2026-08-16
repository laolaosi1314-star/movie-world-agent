# 《影视世界 Agent》总控蓝图（CAD 图 / 沟通记录）

> 用途：把截至 2026-08-16 的全部设计决策、架构、表结构、接口约定汇总为一份"图纸"，
> 便于后续返工、评审与接手。所有代码以本文 + 各 `Phase*` 设计文档为准。
> 标记【返工点】之处为占位/待细化，是后续最可能改动的地方。

---

## 0. 项目一句话

AI Agent 驱动的"虚拟影视行业世界模拟"应用：用户创造/进入世界 → 世界按真实时间线自动演化 → 用户观察/参与/干预。核心不是数据库 + 聊天框，而是**有因果、有记忆、长期运行的世界引擎**。

---

## 1. 已确认的关键原则（不可轻易推翻）

1. 这是"世界"不是数据库；系统须形成循环（人物→作品→市场→人物…）。
2. 时间是核心机制（年/月/日，可推进/暂停）。
3. **禁止纯随机**：RNG 只产出有界意外噪声并记为事件；结果须有因果。
4. Agent 须有记忆（短期/长期/世界），不能每月重新认识世界。
5. 人物/作品须有连续历史（追加写入，可生成传记）。
6. 模块化：UI / 世界模拟 / Agent / DB / 时间 / 事件 / AI 模型 分离，AI 模型可替换。
7. **多存档并存**：旧档转只读存档不删除；所有 API 必传 `world_id`。

---

## 2. 技术栈（易上手优先）

| 层 | 选型 |
|---|---|
| 语言 | Python 3.13 |
| Web | FastAPI |
| ORM/迁移 | SQLAlchemy 2.x + Alembic |
| 数据库 | PostgreSQL 16（`jsonb` + 枚举） |
| AI 适配 | `LLMClient` 抽象接口；Phase 1 = `RuleBasedClient` 占位，后期接真实 LLM 不改业务 |

---

## 3. 目录结构（当前已落地）

```
movie_world_agent/
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 0001_initial.py             # MW + Phase1 全部核心表
│       ├── 0002_phase2_phase3.py       # Phase2/3：公司/市场/电影节/奖项 + 收口 FK
│       ├── 0003_phase4.py              # Phase4：媒体机构/新闻系统
│       ├── 0004_phase5.py              # Phase5：memories 表扩展（衰减字段）
│       ├── 0005_add_award_type.py      # 前置：负面奖项（award_type 枚举 + 两列）
│       └── 0006_award_domain.py        # 【设计✅/编码待做】多领域奖项：work_domain 枚举 + awards/award_categories/ProjectType/CharacterType 扩展（见 §15）
├── app/
│   ├── main.py                         # FastAPI 入口（直接 include 13 个子路由 + 全局 /health,/llm/status）
│   ├── db/{base,session}.py            # Base + engine/Session
│   ├── models/                         # ORM（enums/world/character/project/event/misc/
│   │                                  #      company/market/festival/award/media/news）
│   ├── schemas/                        # Pydantic（world/character/project/event/
│   │                                  #      company/market/festival/award/media/news/report/memory）
│   ├── api/                            # deps + routers(worlds/characters/projects/
│   │                                  #      companies/markets/festivals/awards/sim/events/
│   │                                  #      media/news/reports/memories)
│   ├── sim/                            # engine + character/project/company/market/
│   │                                  #      festival/award/media agents + util + memory
│   └── llm/client.py                   # LLMClient 接口 + RuleBasedClient 降级 +
│                                      #      OpenAICompatibleClient(真实 provider, httpx 直连) +
│                                      #      get_llm_client() 一键切换 + get_llm_status() 诊断
├── requirements.txt
├── .env.example                        # LLM_* 配置示例（复制为 .env 填写，不提交密钥）
├── LOCAL_GUIDE.md                      # 本地运行/迁移/启动/闭环验证指南
├── run_smoke_test.py                   # 零依赖冒烟脚本
├── test_phase5_memory.py               # Phase5 记忆衰减/权重单测
├── test_phase7_llm.py                  # Phase7 LLM 接入/降级/配置单测
├── test_negative_awards.py             # 前置：负面奖项判定/尖锐话题单测
└── BLUEPRINT.md                        # 本文件
```

---

## 4. 数据库 Schema 汇总（首版迁移已含）

| 表 | 归属 | 关键字段 |
|---|---|---|
| `world` | MW | current_year/month, industry_status, status(active/archived), seed_config |
| `simulation_ticks` | MW/时间 | world_id, tick_index, unit, from/to_date, rng_seed_used |
| `characters` | P1 | world_id, type, name, status, career_stage, attributes(jsonb), is_in_hall_of_fame |
| `character_attribute_log` | P1 | character_id, field, old/new_value, reason（防失真留痕） |
| `character_career_history` | P1 | character_id, year, month, title（追加式时间线） |
| `relationships` | P1 | world_id, from/to_type+id, relation（通用边） |
| `projects` | P1 | world_id, type, title, status(生命周期), quality_metrics(jsonb) |
| `project_cast` | P1 | project_id, character_id, role, billing |
| `events` | P1 | world_id, tick_id, level, causal_chain(jsonb), is_historic |
| `interventions` | 上帝模式 | world_id, target_type/id, field, old/new_value, reason（审计） |
| `memories` | P5落地 | world_id, agent, scope(short/long/world), key, value, importance, access_count, last_accessed_tick, expires_tick, is_dormant |
| `companies` / `company_history` | P2 | 公司生命周期 + 追加式历程 |
| `market_snapshots` / `project_market` | P2 | 市场环境快照 + 单作品票房（factors 可解释） |
| `festivals` / `festival_editions` / `festival_selections` / `festival_awards` | P3 | 电影节/届次/单元/颁奖 |
| `awards` / `award_seasons` / `award_categories` / `nominations` / `winners` | P3 + 前置 | 奖项档案/奖季/类别/提名/获奖；`awards`/`award_categories` 新增 `award_type`(positive/negative) 区分正/负奖；预留 `domain` 列支持电视/音乐跨界（见 §15） |
| `award_season_stats` / `award_achievements` | P3 | 每届叙事标签 + 人物×奖项成就累计 |
| `media_outlets` | P4 | 媒体机构：outlet_type/stance/credibility/preferred_categories（舆论多样性来源） |
| `news` | P4 | 报道条目：fact_pack(jsonb 原样存) + render_engine(template/llm) + outlet_snapshot |

> 当前表总数：**28**（verify_imports 实测）。Phase 4 由 `0003_phase4` 迁移创建 `media_outlet_type`/`media_stance`/`news_type`/`render_engine` 四个枚举。
> Phase 5（`0004_phase5`）不新增表，而是在既有 `memories` 表上扩展 `importance`/`access_count`/`last_accessed_tick`/`expires_tick`/`is_dormant` 五列，
> 支撑"写入/检索/巩固/过期/遗忘"机制；`memories` API 新增于 `app/api/memories.py`（13 个业务子路由）。
> 前置（Phase 6 前）由 `0005_add_award_type` 迁移创建 `award_type` 枚举，并向 `awards`/`award_categories` 各加一列（默认 positive，兼容既有行），不新增表。
> 多领域扩展（见 §15）规划由 `0006_award_domain` 迁移新增 `work_domain` 枚举，并向 `awards`/`award_categories` 各加 `domain` 列（默认 film，兼容既现行电影奖行）、扩展 `ProjectType`(+ALBUM/SINGLE) 与 `CharacterType`(+SINGER)、给 `project_market` 增加 `domain` 与电视收视率/音乐销量·流媒体·榜单指标列；不新增表，向后兼容。

> 注：`awards`/`award_seasons`/`nominations`/`winners` 在 Phase 1 设计文档称"已建表埋点"，
> 但 `0001_initial` 实际未创建，已在 `0002_phase2_phase3` 中正式建表（见【返工点】#10）。
> `characters.company_id`、`projects.company_id` 在 0002 收口为正式 FK；`projects` 新增 `distribution_company_id`。

---

## 5. 接口约定（强制）

- 所有业务资源挂在 `/worlds/{world_id}/...` 下，`world_id` 为必传路径参数。
- 读操作：任意状态世界均可。
- 写操作（POST/PUT/DELETE/PATCH，含 `/sim/advance`、上帝模式）：依赖 `require_writable_world`，
  `archived` 世界返回 **423 Locked**。
- 多世界完全隔离：列表/查询最终按 `world_id` 过滤。

已实现端点：
`GET/POST /worlds`、`GET /worlds/{id}`、`POST /worlds/{id}/archive`、`POST /worlds/{id}/clone`、
`GET/POST /worlds/{id}/characters`、`GET/POST /worlds/{id}/projects`、
`POST /worlds/{id}/sim/advance`、`GET /worlds/{id}/events`、
`GET/POST /worlds/{id}/media-outlets`、`GET/PATCH /worlds/{id}/media-outlets/{outlet_id}`、
`GET /worlds/{id}/news`、`POST /worlds/{id}/news/{news_id}/rerender`、
`GET /worlds/{id}/reports/{monthly|quarterly|annual}`。
全局（无 world_id）：`GET /health`、`GET /llm/status`（LLM 诊断，不含密钥）。

---

## 6. 阶段进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 设计 | 产品方案 + Phase1/2/3 设计 + MW 设计 | ✅ 完成 |
| Phase 0 | 工程骨架 + 多世界 + Phase1 ORM/迁移/路由/Tick/创建 | ✅ 代码落地 |
| Phase 2 | 公司系统 + 票房因果模型 | ✅ ORM/迁移/路由/Sim 编码落地（规则占位） |
| Phase 3 | 电影节 + 奖项体系 | ✅ ORM/迁移/路由/Sim 编码落地（规则占位） |
| Phase 4 | 媒体/新闻/事件深化 | ✅ ORM/迁移/路由/Sim 编码落地（FactPack+模板渲染+LLM插槽+报告聚合） |
| Phase 5 | 长期记忆三层完整落地 | ✅ 写入/检索/巩固/短期过期/长期遗忘 + 接入人物决策与 FactPack |
| 前置(Phase6前) | 负面奖项体系（金酸梅式） | ✅ AwardType 枚举 + 负面判定算法 + 尖锐话题→争议通稿 |
| Phase 3.x | 多领域/跨界奖项（电视·音乐）扩展 | ✅ 设计（§15）+ 编码落地（迁移 0006 + 通用化 Agent + 种子三领域奖项 + 单测全绿） |
| 移动端基建 | 无状态 API + App/H5 对接契约 | ✅ 无状态已贯彻；新增 CORS 中间件（env 可控）+ `API_CONTRACT.md` 契约文档 |
| Phase 6 | 用户角色体系 | 🟢 进行中（身份模型/角色边界已落地 §16；业务动作绑定 + 玩家视角接口已落地 §16.7；后续社会与商业生态链演进路线见 §17） |
| Phase 7 | 接入真实 LLM provider（表达层）+ World Director 冲突校验 | ✅ LLM provider 接入（OpenAI 兼容 / 一键降级）；⏳ World Director 冲突校验待做 |
| Phase 8 | 完整 UI 优化 | ⏳ 未开始 |

---

## 7. 【返工点 / 待细化】—— 后续最可能改动处

1. **规则引擎占位**：`character_agent`/`project_agent`/`company_agent`/`market_agent`/`festival_agent`/`award_agent`
   均用确定性有界规则演示架构，真实因果 AI 逻辑须通过 `LLMClient` 注入（Phase 7）。返工概率：高。
2. **`clone` 仅复制世界元信息**：实体（人物/作品/事件）深拷贝未实现，仅建了新 world 行。
   若需"基于当前设定开新档"，需补 SQL 级深拷贝。返工概率：中。
3. **`agent_id` 未加 FK**：指向经纪人人物，为避免循环依赖暂未强制外键（companies 已加 FK）。返工概率：低。
4. **报告聚合已落地（原返工点已解决）**：Phase 4 的 `generate_report` 已实现月/季/年报，
   数字来自 DB 真实查询（票房冠军/重大事件/争议/年度作品量/行业环境），与 world 一致。
   可深化：奖项总结/电影节总结/最热演员等需在 Phase 3 数据更丰富后补充 section。返工概率：低。
5. **事件因果链偏薄处**：票房/奖项已接入多因子 `factors`/`causal_chain`，但人物演化仍仅是 heat 扰动占位。返工概率：中。
6. **无 World Director 冲突校验**：`engine.py` 末尾 TODO 位置未实现多 Agent 写入冲突校验（LLM provider 接入已于 Phase 7 完成，见 §13，仅用于表达层，不碰判定链）。返工概率：高。
7. **无自动化长跑验证脚本**：Phase 1 任务 I（5 年模拟验证不变量）尚未以 pytest/脚本方式落地。返工概率：中。
8. **`World` 模型 Enum 未显式命名**：依赖 Alembic 为真理源（未启用 `create_all`），若将来切 `create_all` 需给模型 Enum 补 `name=`。
9. **汉字 server_default**：`world.name`/ `industry_status` 默认值含中文，Postgres 下正常；若换数据库需注意编码。
10. **awards 系列表缺失返工**：Phase 1 设计文档称 `awards`/`award_seasons`/`nominations`/`winners` "已建表埋点"，
    但 `0001_initial` 实际未创建。Phase 3 编码时在 `0002_phase2_phase3` 中正式建表并启用逻辑。
    若之前误以为这些表存在而依赖它，需回归检查。返工概率：中。
11. **电影节/奖项类别未区分男女演员**：规则占位用"最佳主演"；若人物 `attributes.gender` 为 male/female
    则 award_agent 会细分男女演员奖。建议后续给 `Character` 增加正式 `gender` 列（需小迁移）。返工概率：中。
12. **`Nomination`/`Winner` 的 `category_id` 用 0 占位**：因预定义类别未落 `award_categories`，
    查询历届回顾按 `category_name` 聚合。若启用 `award_categories` 正式流程需回填 category_id。返工概率：低。
13. **奖项体系强耦合电影领域**：当前 `AwardAgent` 仅用 `project_market`(票房分项) 与"最佳影片"类目，且 `_released_with_crew` 不区分 `Project.type` 领域；`ProjectType` 虽含 TV/WEBSERIES 但无电视收视率/音乐榜单数据源，音乐领域甚至无对应 `ProjectType`。跨界扩展设计见 §15（domain 轴 + 通用 `WorkEvaluator`）。返工概率：高（Phase 3.x 落地时）。

---

## 8. 运行方式（供返工/联调）

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/movie_world"
alembic upgrade head
uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000/docs 查看全部带 world_id 的接口
```

示例链路：
1. `POST /worlds` 创建存档 → 得到 `world_id`。
2. `POST /worlds/{id}/characters` 创建人物。
3. `POST /worlds/{id}/news...` 实际上是 `POST /worlds/{id}/projects` 创建作品。
4. `POST /worlds/{id}/sim/advance` 推进时间，观察 `events` 与人物属性演化。
5. `POST /worlds/{id}/archive` 把该档设为只读；再 `POST /worlds` 开新档，互不影响。

---

## 9. 变更记录（CAD 修订历史）

- v0.1（2026-08-16）：初始蓝图，落地 MW + Phase1 骨架。
- v0.2（2026-08-16）：编码落地 Phase 2（公司/市场票房因果模型）+ Phase 3（电影节/奖项体系）。
  新增枚举/ORM/迁移 0002/Schemas/四个 Sim Agent（接入 engine）/四个 API 路由（含 world_id 与只读锁、上帝模式 override）。
  修正：awards 系列表在 0002 正式建表；characters/projects 的 company_id 收口 FK，projects 新增 distribution_company_id。
- v0.3（2026-08-16）：新增 `LOCAL_GUIDE.md` 与 `run_smoke_test.py`。移除 `app/api/router.py` 中间层，`main.py` 直接 include 9 个子路由。TestClient 实测全部业务路由命中（无 404）。
- v0.4（2026-08-16）：落地 **Phase 4 媒体/新闻/事件深化 + LLM 接入契约定型**：
  新增 models/media.py(`MediaOutlet`)、models/news.py(`News`)；schemas(media/news/report)；
  sim/media_agent.py（FactPack 构建器 + 模板渲染器 + LLM 插槽 + 报告聚合器）并接入 engine；
  api(media/news/reports) 注册到 main；迁移 0003 创建 4 个枚举 + media_outlets/news 两表（总表 28）。
  **关键架构决策**：LLM 仅允许在"表达层"（render_narrative），禁止参与任何判定；fact_pack 原样存 jsonb 以便未来重渲染；
  LLM 不可用自动降级模板，世界演化不受影响。详见新增 §11。
- v0.5（2026-08-16）：落地 **Phase 5 长期记忆三层（短期/长期/世界）**：
  迁移 `0004_phase5` 在 `memories` 表扩展 `importance`/`access_count`/`last_accessed_tick`/`expires_tick`/`is_dormant`；
  新增 `app/sim/memory.py`（MemoryStore + MemoryAgent：写入/检索权重/巩固/短期过期/长期遗忘，确定性、多世界隔离）；
  打通 `character_agent`（记忆偏置决策 + 沉淀动量）、`award_agent`（写入荣誉记忆）、`media_agent.build_fact_pack`（memory_context 注入表达层）；
  新增 `app/api/memories.py`（13 号路由）并接入 `main.py`；`engine` 末尾统一调度记忆维护。
  离线验证：`verify_imports.py`（递归校验记忆路由/字段）、`test_phase5_memory.py`（衰减/权重/阈值单测）全绿；表总数保持 28。详见新增 §12。
- v0.6（2026-08-16）：落地 **Phase 7 之「接入真实 LLM provider（表达层）」**（World Director 冲突校验仍待做）：
  重写 `app/llm/client.py`：保留 `LLMClient` ABC 与 `RuleBasedClient` 降级；新增 `LLMConfig`、极简 `.env`（仅 `LLM_*`）读取、
  `load_llm_config`、`OpenAICompatibleClient`（基于 `httpx` 直连 OpenAI 兼容 `/chat/completions`，兼容 OpenAI/DeepSeek/Moonshot/智谱/本地 vLLM/Ollama）、
  `build_narrative_messages`（§11 合规提示词：只渲染不判定不编造）、`get_llm_client(force_template)` 一键切回模板、`get_llm_status` 诊断。
  新增全局 `GET /llm/status`（无密钥）；`news.rerender` 支持 `force_template`。新增 `.env.example`、`test_phase7_llm.py`。
  离线验证：`verify_imports.py` 校验 LLM 接线；`test_phase7_llm.py` 全绿（禁用降级 / 提示词合规 / `_post` 失败降级 / `.env` 读取 / `force_template`）。详见新增 §13。
- v0.12（2026-08-16）：**§17.3 舆论与危机公关——底层逻辑落地（黑料爆料·丑闻演化·多阶段公关）**：新增枚举 `scandal_type`/`scandal_stage`/`pr_strategy`；模型 `scandals`(world_id/character_id/severity/evidence_strength/is_confirmed/stage/heat/public_opinion/各 tick 锚点) 与 `crisis_pr`(strategy/by_player_id/impact 结算)；迁移 `0009_scandal_crisis`（纯新增两表+三枚举，并向 `intervention_type` 扩展 `scandal`/`crisis_pr`，向后兼容）；`app/sim/crisis_agent.py` 实现确定性状态机（LATENT→SPREADING→ERUPTED→RESOLVING→RESOLVED/COLLAPSED）+ `evaluate_pr` 舆论恢复曲线（冷处理/律师函/道歉/买热搜/洗白反转 各有胜负手）；**无缝复用 §14 闭环**：爆发产「丑闻争议」事件经媒体 Agent 生成 CONTROVERSY 新闻、写入 `sharp_topics`(domain=crisis) 由媒体下一 tick 生成争议通稿、塌房写 `char:{id}:notorious` 注脚；`_badness` 桥接 `scandal_reputation_penalty()` 使丑闻缠身者更易被金酸梅点名；危机 Agent 接入 `engine` 每 tick 调度；路由 `app/api/crisis.py`（create/expose/pr/list/detail/pr-history，crisis:manage 网关 + Intervention 审计 + 423 只读锁）；`roles.py` 新增 `PERM_CRISIS_MANAGE`(GM，写类) 与 `ACTION_CATALOG` 条目。**权限/契约零破坏**：verify_imports 全 True、pytest **68 项全绿**（52 既有 + 16 §17.3）。详见 §17.3、LOCAL_GUIDE §6.12。
- v0.13（2026-08-16）：**§17.1 商业时尚与塌房违约金——底层逻辑落地（与 §17.3 强耦合）**：新增枚举 `endorsement_tier`/`contract_status`/`magazine_tier`；模型 `endorsements`(world_id/character_id/brand_name/tier/annual_fee/penalty_rate/has_morals_clause/signed_tick/duration_ticks/status/terminated_tick/penalty_amount) 与 `magazine_covers`；`characters` 加 `commercial_value` 列（并镜像进 attributes 供市场 Agent 读取）；迁移 `0010_commercial`（纯新增两表+三枚举+加列，向后兼容）；`app/sim/commerce_agent.py` 实现**确定性自动商务**（高热度艺人按 propensity 接洽代言/封面，cap 限流、塌房人物不再接约）+ `apply_collapse_penalty`（塌房瞬间遍历带道德条款的生效代言→`breached` 并按 `penalty_rate×剩余年限` 计赔、商业价值按严重度重挫、取消未刊登封面、写「商业塌房」事件 + §14 复用 `sharp_topics`(domain=commerce)）；**桥接点**：`CrisisAgent` 在 `COLLAPSED` 时调用 `apply_collapse_penalty`，把"黑料/塌房"与"真金白银"焊死；路由 `app/api/commerce.py`（endorsements/covers 列表、GM 签约/解约/安排封面、商业概览，commerce:manage 网关 + Intervention 审计 + 423）；`roles.py` 新增 `PERM_COMMERCE_MANAGE`(GM，写类) 与 `ACTION_CATALOG` 条目；**顺带修复** `main.py` 此前未将 `crisis.router` 纳入挂载循环（§17.3 的 HTTP 路由实际未注册）的注册漏洞，并一并挂上 `commerce.router`。**权限/契约零破坏**：verify_imports 全 True、pytest **77 项全绿**（68 既有 + 9 §17.1）。详见 §17.1、LOCAL_GUIDE §6.13。
- v0.14（2026-08-16）：**§17.2 人际关系与情感网络 + 人生档案馆——底层逻辑落地（三大生态链收官）**：新增枚举 `romance_type`/`romance_status`；模型 `romances`(world_id/character_a_id/character_b_id/romance_type/status/is_public/publicness/reacted_tick/child_count/各 tick 锚点/ended_reason)；迁移 `0011_relationship`（纯新增两表枚举+romances 表，向后兼容）；`app/sim/romance_agent.py` 实现确定性 `fan_profile`(偶像依赖度) + `compute_fan_reaction`(脱粉 vs 应援 蝴蝶效应，绯闻未坐实仅涨话题、偶像型公开婚恋大幅脱粉且≥70 触发回踩) + `RomanceAgent` 每 tick 演化（自然曝光泄露达阈值自动公开结算、与 §17.3 桥接：一方出轨丑闻自动拆散关系并脱粉）；`app/sim/life_archive.py` 只读聚合「人生档案馆」(`build_archive` 结构化历年奖项/商业/丑闻/情感/生涯/重大事件 + 合并时间轴，`legacy_footnotes` 读取长期记忆实现"随岁月沉淀动态渲染")；**桥接点**：出轨拆散读 §17.3 `Scandal`（零改动 CrisisAgent），公开/回踩/分手写「情感争议」事件 + §14 复用 `sharp_topics`(domain=relationship)（媒体 Agent 零改动），脱粉镜像贬值商业价值（与 §17.1 同源）；路由 `app/api/romance.py`（relationships 列表/编排/reveal/add-child/end + characters/{id}/archive 人生档案馆，relationship:manage 网关 + Intervention 审计 + 423）；`roles.py` 新增 `PERM_RELATIONSHIP_MANAGE`(GM，写类) 与 `ACTION_CATALOG` 条目。**权限/契约零破坏**：verify_imports 全 True、pytest **89 项全绿**（77 既有 + 12 §17.2）。详见 §17.2、LOCAL_GUIDE §6.14。
- v0.7（2026-08-16）：**Phase 6 前置——负面奖项体系（金酸梅式）** 落地：
  迁移 `0005_add_award_type` 新增 `award_type(positive/negative)` 枚举并扩展到 `awards`/`award_categories` 两表（默认 positive，兼容既有行）；
  `AwardAgent` 增加负面类别（`最差影片/导演/男女演员/编剧`）与确定性负面判定算法 `_badness`（低 composite_quality + 低 audience_score/media_score + 高开低走轨迹，越大越烂），
  负奖颁奖事件类别为"负面奖项"；负奖结果写入世界记忆 `sharp_topics`，`MediaAgent` 召回并生成"尖锐话题"争议通稿（即时 + 后续），负奖人物记"notorious"记忆；
  新世界自动播种金屏奖 + 金酸梅奖。新增 `test_negative_awards.py`（全绿）、`verify_imports` 增加 award_type 校验。详见 §14。

---

- v0.8（2026-08-16）：**多领域/跨界奖项体系（电视·音乐）扩展方向——蓝图设计（未编码）**：在 BLUEPRINT 新增 §15，确立「领域(domain)×正副(award_type)×类目客体(kind)」三正交轴；规划 `work_domain` 枚举、`awards`/`award_categories` 的 `domain` 列、`ProjectType`(+ALBUM/SINGLE) 与 `CharacterType`(+SINGER) 扩展、`project_market` 增加 `domain` 与电视收视率/音乐销量·流媒体·榜单指标列（迁移 0006，向后兼容，不新增表）；评奖 Agent 通用化为 `_eligible_works(domain)` + `WorkEvaluator(domain)` + 分域 `CATEGORY_DEFS`；论证与 sharp_topics/honor 记忆/成就累计/媒体争议 等既有机制天然兼容（domain 无关）。详见 §15。
- v0.9（2026-08-16）：**§15.6 多领域奖项扩展——编码落地（向后兼容、不新增表）**：新增 `WorkDomain`/`CategoryKind` 枚举；`ProjectType`(+ALBUM/SINGLE) 与 `CharacterType`(+SINGER) 扩展（迁移 0006 用 `ALTER TYPE ADD VALUE`）；`awards`/`award_categories` 加 `domain`、`award_categories` 加 `kind`（默认 film/project，按名回填既有行）；`project_market` 加 `domain`/`rating`/`sales`/`streams`/`chart_position`（均 nullable）；`award_agent` 通用化为 `_eligible_works(domain)` + `WorkEvaluator` + `CATEGORY_DEFS[(domain,award_type)]` + 扩展 `_pick`（歌手/专辑/单曲/作词/作曲），种子新增 金屏剧奖(tv 正)/金唱片奖(music 正)/金酸梅剧奖(tv 负)/金扫帚奖(music 负)；保留旧 `POSITIVE/NEGATIVE_CATEGORY_DEFS` 别名后向兼容；API 创建奖项/类别写入 `domain`/`kind` 并做 422 校验；单测 `test_multidomain_awards.py` 与 `verify_imports` 全绿。**移动端基建**：API 明确无状态（world_id 隔离、请求级会话、无会话态）；`app/main.py` 增加 env 可控 `CORSMiddleware`；新增 `API_CONTRACT.md`（无状态 + App/H5 对接契约，含 Phase 6 用户角色扩展点）。详见 §15、LOCAL_GUIDE §6.9。
- v0.10（2026-08-16）：**Phase 6（一）用户角色体系——身份模型与角色边界编码落地**：新增 `PlayerRole` 枚举(audience/critic/investor/gm)；新增 `players` 表（迁移 `0007_player_roles`，`player_role` 枚举 + `player_key` 唯一索引 + `critic_domains` jsonb）；`app/auth/roles.py` 声明式权限矩阵（`role → permission`）+ `critic_can_create_award()` 领域限定 + `WRITE_PERMISSIONS`（触发 423 只读锁校验）；`app/api/deps.py` 增加无状态令牌解析（`get_player`/`get_player_optional`/`require_permission` 工厂，Bearer 解析 + world 作用域隔离）；`app/api/players.py` 实现玩家 CRUD + GM 自举/授权边界 + `/me` + 停用/启用(GM)；`API_CONTRACT.md` §7 具体化（401/403 错误码、Bearer 解析流）；`test_phase6_identity.py` + `verify_imports` 全绿。详见 §16。
- v0.11（2026-08-16）：**Phase 6（二）业务动作绑定 + 玩家视角/能力接口落地**：四个核心动作接入 `require_permission`——`sim/advance`(PERM_SIM_ADVANCE，任何角色可推进)、`awards.override_winner`/`festivals.override_award`(PERM_WORLD_INTERVENE，且 `Intervention.user_id=str(player.id)` 归因到 GM 玩家，原默认 'god')、`awards.create_award/create_category`(PERM_AWARD_CREATE + critic 领域闸门 403)、`POST /projects/{id}/financing`(PERM_PROJECT_INVEST，记录 `Intervention(FINANCING)`、状态迁 FINANCING、`quality_metrics` 累加 financing_total/financings)；新增 `InterventionType.FINANCING`（迁移 `0008_intervention_financing`）；**设计修正** `PERM_PLAYER_ADMIN` 不纳入世界 423 锁（账号级操作）；客户端动作目录 `ACTION_CATALOG` + `capabilities_of(role)`；`/me`→`PlayerMeOut`(capabilities+actions)、`/me/portal`→`PlayerPortalOut`(身份+世界快照+近期 timeline)；`verify_imports` 新增 Phase6(二) 校验；`test_phase6_actions.py`（13 项全绿），与既有合计 **52 项单测全绿**。BLUEPRINT 新增 **§17 后续演进路线：社会与商业生态链**（商业时尚/人际情感/舆论公关三大链，复用 §11·§14·Intervention 闭环）。详见 §16.7、§17。

## 15. 多领域 / 跨界奖项体系扩展方向（电视·音乐）

> 目标：奖项体系不止服务电影，也能评"电视类（视帝/视后/最佳剧集）"与"音乐类（最佳专辑/单曲/男女歌手）"，并允许单一奖项跨领域（如"金屏奖"同时含电影、电视、音乐类别）。本节约等于施工图，编码阶段按 §15.6 清单落地即可。全程遵守 §11；负奖跨领域同样走 §14 的 sharp_topics→争议通稿闭环。

### 15.1 现状耦合点（为何需要扩展）
1. **领域写死在电影**：`AwardAgent._released_with_crew()` 取所有 `status=released` 的 `Project`，不区分 `type`；评分只来自 `project.composite_quality` + `project_market`（票房分项）。
2. **类目写死电影**：`POSITIVE_CATEGORY_DEFS`/`NEGATIVE_CATEGORY_DEFS` 仅 最佳/最差影片·导演·男/女演员·编剧。
3. **电视/音乐缺数据源**：`ProjectType` 虽有 `TV`/`WEBSERIES` 但无"收视率"口径；音乐甚至无对应 `ProjectType`（缺专辑/单曲），也无销量/流媒体/榜单数据。
4. **负奖已正交**：`award_type` 与领域无关，正交良好；扩展后"最差剧集/最差专辑"可自然复用 §14 算法。

### 15.2 三个正交轴（核心抽象）
| 轴 | 取值 | 落点 | 说明 |
|---|---|---|---|
| **领域 domain** | `FILM` / `TV` / `MUSIC` | `AwardCategory.domain`（权威源）；`Award.domain` 仅作标签/默认 | 区分被评的是电影/电视/音乐 |
| **正副 award_type** | `POSITIVE` / `NEGATIVE` | 既有 `Award.award_type` | 表彰 vs 吐槽，与领域正交 |
| **类目客体 kind** | 见 §15.3 `CategoryKind` | `AwardCategory.kind` | 该类别评判的客体（作品/导演/演员/歌手…） |

- **跨界无缝**：`domain` 落在「类别」粒度，因此**同一奖项可混合不同领域类别**（金屏奖 = 电影类 + 电视类 + 音乐类）。引擎按各类别自身 `domain` 取候选与评分，互不影响。
- `Project.type` → `domain` 映射（Agent 内常量）：`FILM→film`；`TV`/`WEBSERIES`/`VARIETY→tv`；`ALBUM`/`SINGLE→music`。余者（animation/documentary/short）暂挂 `film`，扩展时再定。

### 15.3 数据模型变更（迁移 `0006_award_domain`，向后兼容、不新增表）
**(a) 枚举扩展**
- 新增 `WorkDomain(str, enum.Enum)`：`FILM="film"` / `TV="tv"` / `MUSIC="music"`。
- `ProjectType` 新增 `ALBUM="album"` / `SINGLE="single"`（音乐作品复用工程统一表 `projects`，无缝）。
- `CharacterType` 新增 `SINGER="singer"`（音乐人；作词/作曲沿用 `WRITER`/`COMPOSER`）。
- （建议）新增 `CategoryKind(str, enum.Enum)` 取代散落字符串，取值见下表；最小改动亦可仅扩展字符串白名单。

**(b) `awards` / `award_categories` 增加列**
| 表 | 新增列 | 类型 | 默认 | 兼容 |
|---|---|---|---|---|
| `awards` | `domain` | `Enum(work_domain)` | `film`(`server_default='film'`) | 既正/负电影奖行保持 `film` |
| `award_categories` | `domain` | `Enum(work_domain)` | `film` | 同上 |
| `award_categories` | `kind` | `Enum(category_kind)` 或 `String` | `project` | 既现行按名回填（最佳影片→project…） |

**(c) 市场表现泛化（`project_market` 加列，不再只服务票房）**
保持表名不变避免重命名震荡，语义扩展为"作品市场/口碑表现"：
| 新增列 | 含义 | 适用 domain |
|---|---|---|
| `domain` | 该条表现所属领域 | 全部 |
| `rating` | 收视率（%） | tv |
| `sales` | 销量（万） | music |
| `streams` | 流媒体播放（万次） | music |
| `chart_position` | 榜单最高名次 | music |
| （既有）`box_office`/`audience_score`/`media_score`/`word_of_mouth_trajectory` | 电影沿用 | film |
- 电影既现行 `domain=film` 照常；电视/音乐行填各自列、电影列留 NULL。`WorkEvaluator` 按 `domain` 选指标（§15.4）。
- `audience_score`/`media_score` 三领域通用，复用为"口碑分"；音乐可映射为"乐评/听众分"。

**(d) `CategoryKind` 全集（按领域）**
| domain | kind 取值与含义 |
|---|---|
| film | `project`(最佳影片) / `director` / `actor_male`(影帝) / `actor_female`(影后) / `writer`(编剧) |
| tv | `project`(最佳剧集) / `director` / `actor_male`(视帝) / `actor_female`(视后) / `writer`(编剧) |
| music | `album`(最佳专辑) / `single`(最佳单曲) / `singer_male`(最佳男歌手) / `singer_female`(最佳女歌手) / `lyricist`(最佳作词) / `composer`(最佳作曲) |

### 15.4 评奖 Agent 通用化（落地要点）
1. **候选筛选**：`_released_with_crew()` → `_eligible_works(domain)`，按 `Project.type→domain` 映射过滤（电视类只看 TV/WEBSERIES 作品，音乐类只看 ALBUM/SINGLE）。
2. **评分器抽象**：新增 `WorkEvaluator(domain)`，返回 `{quality, audience_score, media_score, extra}`：
   - film：沿用 `composite_quality` + `project_market` 票房分项（现状）。
   - tv：`quality` 由口碑/评分合成，`audience_score`←`rating`（收视率归一），`extra` 含集数等。
   - music：`quality`←乐评分，`audience_score`←听众分（流媒体/销量归一），`extra` 含榜单名次。
   - `_badness`（§14.2）保持通用，仅喂入对应 `domain` 的 quality/audience/media/trajectory，负奖跨领域直接复用。
3. **类目定义表驱动**：`CATEGORY_DEFS[(domain, award_type)] → [ {name, kind}, ... ]`，替代现有两套硬编码列表；`_run_season` 按 `category.domain` 取对应定义。
4. **`_pick(kind, entry)` 扩展**：新增 `singer_male`/`singer_female`（取 `CharacterType.SINGER` 并按 `attributes.gender` 细分）、`album`/`single`（kind=project 时按作品 type 区分专辑/单曲）、`lyricist`/`composer`（取 `WRITER`/`COMPOSER`）。无对应客体则不产生该类别候选（同现状的演员性别回退）。
5. **事件/叙事**：事件层（`category="奖项"`/`"负面奖项"`、标题含奖项名与届次、描述含 类别→客体 标签）**领域无关**，无需改动；`AwardSeasonStat`(最大赢家/最年轻…) 与 `AwardAchievement`(X提Y中) 亦领域无关，自动覆盖。

### 15.5 与既有机制的兼容性（天然无缝）
- **sharp_topics / 媒体争议（§14.3）**：写入的是 headline+target，与领域无关；电视/音乐负奖（最差剧集/最差专辑…）自动进入争议通稿闭环，媒体 Agent 无需改动。
- **honor / notorious 记忆（§14.3、§12.3）**：按 `character` 键，跨领域自动累计；音乐人/电视剧演员获奖同样沉淀荣誉记忆。
- **成就累计（§14.2/§14.4）**：`AwardAchievement` 已是 `(award, character)` 粒度，跨领域奖项自然累计；若奖项跨领域过多，可后续细化到 `(award, domain, character)`，非必须。
- **Phase 6 用户角色（已落地身份模型与角色边界，见 §16）**："剧评人/音乐评论人"等玩家身份可创建对应 `domain` 的奖项/奖季——由 `Player.critic_domains`（WorkDomain 子集）与 `critic_can_create_award()` 限定；权限边界（`role → permission` 矩阵 + `require_permission` 工厂）沿用 §11 与上帝模式审计（`interventions`）。
- **LLM 仅表达层（§11）**：评分/候选判定全部确定性（WorkEvaluator + 既有 `_badness`），LLM 只渲染 fact_pack，不受影响、不破坏可重放。

### 15.6 实施清单（✅ 编码完成，2026-08-16）
1. `app/models/enums.py`：加 `WorkDomain`、`CategoryKind`；`ProjectType` 加 `ALBUM`/`SINGLE`；`CharacterType` 加 `SINGER`。
2. `app/models/project.py`：无需新表；`ProjectType` 已引用枚举，自动生效。
3. `app/models/award.py`：`Award`/`AwardCategory` 加 `domain`；`AwardCategory` 加 `kind`（枚举或 String）；更新导入。
4. `app/models/market.py`：`ProjectMarket` 加 `domain` + `rating`/`sales`/`streams`/`chart_position`（均 nullable）；更新导入。
5. `alembic/versions/0006_award_domain.py`：建 `work_domain`/`category_kind` 枚举；上述列 `ADD COLUMN ... server_default` 兼容既现行；`ProjectType`/`CharacterType` 用 `ALTER TYPE ADD VALUE`（PG 枚举扩展）。
6. `app/schemas/award.py`：`AwardCreate`/`AwardCategoryCreate`/`AwardOut`/`AwardCategoryOut` 加 `domain` + `kind`（默认 film/project）。
7. `app/api/awards.py`：创建时写入 `domain`/`kind`（含枚举转换）。
8. `app/sim/award_agent.py`：引入 `WorkDomain`/`CategoryKind`；新增 `_eligible_works(domain)`、`WorkEvaluator(domain)`、`CATEGORY_DEFS[(domain,award_type)]`；扩展 `_pick`；`_seed_default_awards` 增 金屏剧奖(TV 正)/金唱片奖(music 正)/金酸梅(TV·music 负类目)。
9. `verify_imports.py`：增 `award_domain_col`/`category_domain_col`/`category_kind_col`/`work_domain_enum_values`/`project_type_has_music` 校验。
10. 单测：扩 `test_negative_awards.py` 或新建 `test_multidomain_awards.py`，验证 分域候选筛选 / 跨领域负奖 badness / 类目 kind 路由 / 种子奖项覆盖；`py_compile` + 离线单测全绿。
11. `LOCAL_GUIDE.md`：补 §6.9 多领域奖项 curl（建电视/音乐奖项、推进跨年、查 `winners` 领域分布与 `sharp_topics`）。
12. 端到端（需本地 PG）：见 LOCAL_GUIDE §6.9。

### 15.7 默认种子奖项（开箱即用，`_seed_default_awards`）
保持"无奖项即播种"体验，新增/扩展：
- `金屏奖`（film 正）+ `金屏剧奖`（tv 正）+ `金唱片奖`（music 正）：各自含对应领域 `CATEGORY_DEFS` 类目。
- `金酸梅奖`（film 负）+ 负类目延伸至 tv/music（最差剧集/最差专辑/最差男·女歌手…），复用 `_badness`。
- 现有单测与 `award_type` 默认 `positive` 不变；新列默认 `film` 保证既现行零迁移冲击。

---

## 10. 已知坑 / 调试记录（避免返工误判）

1. **FastAPI 0.141.1 + Starlette 1.6.0 的 `url_path_for` 对"前缀含路径参数"的路由会误报 `NoMatchFound`**。
   例：`/worlds/{world_id}/characters` 这类路由用 `app.url_path_for('list_characters')` 会抛错，
   但**真实 HTTP 请求路由完全正常**（已用 `TestClient` 验证：返回 DB 连接错误而非 404）。
   → 判断路由是否注册，请用 `TestClient` 真实发请求（看 404 vs 500），不要用 `url_path_for` 或数 `app.routes`。
2. **`app.routes` 计数为顶层数量，含 `_IncludedRouter` 包裹，不能直接反映业务路由数**。
   校验口径：`verify_imports.py` 输出的 `routes_without_world_id: none` 才是关键（确认所有业务路由都挂在世界命名空间下）。
3. **Phase 1 模型曾直接把 Python enum 类传给 `Column`（如 `Column(WorldStatus, ...)`）**，SQLAlchemy 2.x 不接受，
   必须包成 `Enum(WorldStatus, name=...)`；并需 `from sqlalchemy import Enum` 与 `DateTime` 导入。
   已用脚本批量修正，后续新增列务必注意。
4. **`awards` 系列表在 Phase 1 实现里实际未建**（设计文档说"已埋点"），Phase 3 的 0002 迁移已正式建表。

---

## 11. LLM 接入架构约束（长期，禁止绕过）

> 本约束由 Phase 4 定型，**任何后续模块（含 Phase 7 高级 Agent）都必须遵守**。

1. **LLM 只允许站在"表达层"**：把"谁该获奖 / 谁该红"这类**判定**留给确定性因果规则与 `simulation_ticks` 重放机制。
   LLM 只能把已确定的结构化事实（`fact_pack`）渲染成自然语言文本。
2. **判定链不得引入不可重放因素**：一旦 LLM 参与判定，给定 seed 的 tick 重放会得出不同结果，
   直接摧毁防失真最后一道保险。故 `LLMClient.complete`（判定用途）接入时也**不得**写入任何影响世界状态的分支。
3. **`fact_pack` 是唯一事实源**：`news.fact_pack` 原样存 jsonb，文本永远从它渲染。
   未来接了模型后可拿历史 fact_pack **重新生成全部报道**，无需重跑世界（省一次大返工）。
4. **降级是强制的**：`LLMClient.render_narrative` 返回 `None` 或抛异常时，调用方**必须**降级到模板，
   绝不因模型不可用而影响新闻落库或世界演化。
5. **可观测**：`news.render_engine` 标记 `template`/`llm`，`news.outlet_snapshot` 存立场/公信力快照，
   保证同一 fact_pack 的重渲染可复现、可审计。
6. **切换零成本**：接真实 LLM 只需新增一个实现 `LLMClient` 的类并在 `get_llm_client()` 切换；
   业务代码（FactPack/渲染入口/路由）无需改动。可一键切回模板（`LLM_ENABLED=false` 或 `LLM_FORCE_TEMPLATE=true`，
   或 `get_llm_client(force_template=True)`）。详见 §13。

---

## 12. Phase 5 长期记忆三层落地（设计 + 实现）

> 解决核心原则 #4「Agent 须有记忆（短期/长期/世界），不能每月重新认识世界」。

### 12.1 三层语义

| 层 | scope | 生命周期 | 衰减 | 写入方 / 读取方 |
|---|---|---|---|---|
| 短期 | `short` | 按 `expires_tick`/`ttl` 物理过期清理 | 不过问（草稿） | 各 Agent 每 tick 写工作草稿 |
| 长期 | `long` | 持久，受遗忘曲线衰减、可休眠 | 权重 < 阈值标记 `is_dormant` | 由短期巩固而来 / 直接写；跨 tick 被决策读取 |
| 世界 | `world` | 永久（全 Agent 共享） | 永不衰减/休眠 | 任意 Agent 写集体知识；被所有 Agent 读取 |

### 12.2 写入 / 检索 / 衰减机制（`app/sim/memory.py`）

- **写入**：`MemoryStore.write` 按 `(world_id, agent, scope, key)` upsert；短期自动算 `expires_tick = current_tick + ttl`。
- **检索权重**（`retrieval_weight`，确定性、可重放）：
  `权重 = importance × exp(-RECENCY_LAMBDA·age) × (1 + FREQ_FACTOR·ln(1+access_count))`
  - `age = current_tick − last_accessed_tick`；世界记忆权重恒为 1.0。
  - 召回即视为"访问"：命中记忆会刷新 `access_count`/`last_accessed_tick`、解除休眠。
- **巩固**（`consolidate`）：重要度 `≥ CONSOLIDATE_THRESHOLD(0.25)` 的短期记忆提升为长期（重要度向旧值靠拢、值取最新），原短期行删除；低于阈值者留待过期清理。
- **短期过期**（`purge_expired`）：`expires_tick ≤ current_tick` 的短期记忆物理删除（草稿清理，不含历史）。
- **长期遗忘**（`forget_step`）：重算每条长期记忆权重，低于 `DORMANCY_FLOOR(0.08)` 标记 `is_dormant`（保留不删，强线索 `recall_one` 可唤回）。
- 全部按 `world_id` 过滤 → 多世界隔离；超参集中定义便于调参。

### 12.3 与现有流程打通

- **人物决策**（`character_agent`）：tick 初读取"世界记忆(行业气候)"与"自身长期记忆(人气动量/奖项荣誉)"作为确定性偏置（仅调方向/幅度，结果仍钳制 [0,100] 且留痕于 `character_attribute_log`）；tick 中写短期草稿、沉淀"人气动量"长期记忆。形成 记忆→决策→再记忆 的闭环。
- **跨 Agent 记忆**：`award_agent` 颁奖时写"荣誉记忆"(`char:{id}:honor`)，下一 tick 被 `character_agent` 读取为长尾人气偏置。
- **FactPack 表达层**（`media_agent.build_fact_pack`）：召回相关人物长期记忆与"世界记忆"注入 `fact_pack.memory_context`，模板以"（背景：…）"注脚呈现。**仅丰富表达，不参与任何判定，遵守 §11**。
- **引擎调度**：`engine.advance_world` 末尾调用 `MemoryAgent.run()` 统一执行 巩固→过期清理→遗忘，保证每 tick 记忆状态自洽。

### 12.4 接口（`/worlds/{world_id}/memories`，含只读锁）

`GET /`（列表，支持 scope/agent/key/key_prefix/include_dormant）、`GET /{id}`、
`POST /`（上帝模式写入，world 强制 agent=world）、`POST /consolidate`（手动触发巩固/清理/遗忘）、`DELETE /{id}`。

---

## 13. Phase 7 之「接入真实 LLM provider（表达层）」设计 + 实现

> 仅完成"表达层渲染"这一半；World Director 冲突校验（多 Agent 写入协调）仍属待做（见返工点 #6）。

### 13.1 目标与约束
- 让新闻正文可由真实大模型生成（更有可读性），**但只在表达层**：输入是已确定的 `fact_pack`，输出是文本。
- 不引入新 SDK 依赖：用 `httpx`（已装 0.28.1）直连 OpenAI 兼容的 `/chat/completions`，因此 OpenAI / DeepSeek / Moonshot / 智谱 / 本地 vLLM / Ollama(shim) 通用。
- **一键降级**：`LLM_ENABLED=false` 或 `LLM_FORCE_TEMPLATE=true` 或 `get_llm_client(force_template=True)` → 全程模板，零网络请求；任何网络/鉴权/解析错误 → `render_narrative` 返回 `None` → 调用方降级模板。
- 遵守 §11：提示词明确禁止编造事实与做判定；`fact_pack` 是唯一事实源。

### 13.2 配置（环境变量，`app/llm/client.py` 读取 `.env` 仅注入 `LLM_*`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `LLM_ENABLED` | `false` | 是否启用真实 LLM |
| `LLM_FORCE_TEMPLATE` | `false` | 强制模板（一键降级开关） |
| `LLM_PROVIDER` | `openai` | 仅诊断展示 |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容接口前缀 |
| `LLM_API_KEY` | 空 | 密钥，写在 `.env`，不提交 |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名 |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` / `LLM_TOP_P` | `0.7` / `300` / `0.9` | 生成参数 |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | `20` / `1` | 超时秒；仅 5xx 重试 |

### 13.3 调用链
- `MediaAgent._render`：`text = self.llm.render_narrative(fact_pack, outlet_snapshot, news_type.value)`；非 None → `render_engine=llm`，否则 `render_template` + `render_engine=template`。已用 `try/except` 兜底。
- `POST /worlds/{id}/news/{news_id}/rerender?engine=llm|template&force_template=...`：仅重渲染文本，不改 `fact_pack`（事实不变），用于验证插槽切换 / 模板降级。
- `GET /llm/status`（全局，无 `world_id`，无密钥）：返回 `engine=llm|template` 及 `provider/model/base_url`，便于确认当前生效引擎。

### 13.4 切换点
- 接新 provider：新增 `LLMClient` 子类，在 `get_llm_client()` 按 `LLM_PROVIDER` 分支返回；业务代码零改动。
- 降级验证：见 `LOCAL_GUIDE.md` §7 与 `test_phase7_llm.py`。

---

## 14. 负面奖项体系（Phase 6 前置）设计 + 实现

> 目标：在既有正奖（金屏奖）之外，引入"负奖"（金酸梅奖式），表彰烂片/烂表演；
> 其颁奖结果直接成为媒体 Agent 的"尖锐话题"，用于生成充满争议的新闻通稿。
> 全程遵守 §11（LLM 仅表达层，不碰判定链）。

### 14.1 数据模型（迁移 0005_add_award_type）
- 新增枚举 `award_type(positive/negative)`。
- `awards.award_type`、`award_categories.award_type` 两列，默认 `positive`，兼容既有正奖行。
- API：`POST /awards` 与 `POST /awards/{id}/categories` 支持传 `award_type`；输出 DTO 含 `award_type`。
- 开箱即用：若某 world 尚无任何奖项，`AwardAgent._seed_default_awards` 自动播种
  `金屏奖`(正) + `金酸梅奖`(负) 及各自类别，保证奖项体系无需手动建表即可运行。

### 14.2 负面判定算法（`AwardAgent._badness`，确定性、可重放）
对每个已上映作品计算"烂度"分值（越大越烂），全部来自数据库既有事实，无随机：

```
badness = (100 - composite_quality) × 0.5
        + (100 - audience_score)    × 0.3   # project_market.audience_score
        + (100 - media_score)       × 0.2   # project_market.media_score
        + (trajectory == "high_open_low_close" ? 10 : 0)
```

`award_type=negative` 的奖季，对每个负类别取 `badness` 最高的 5 个为提名、最高的为获奖
（正奖则取 `composite_quality` 最高者，逻辑统一为"score 最大者胜"）。

### 14.3 负面奖项 → 媒体 Agent 的"尖锐话题"闭环
1. **即时争议**：负奖颁奖事件 `category="负面奖项"`，媒体 Agent 将其分类为 `CONTROVERSY`
   （`_classify_news_type` 优先判定"负面"子串，避免被"奖项"误判为奖项预测），
   由八卦/毒舌媒体产出争议通稿。
2. **后续争议（尖锐话题）**：`AwardAgent` 同时把负奖结果写入**世界记忆** `sharp_topics`
   （`app/sim/memory.py` 的 world 作用域，永不衰减）。`MediaAgent._generate_sharp_topic_news`
   每个 tick 召回"前序 tick 写入且未消耗"的话题，由八卦/毒舌媒体再生成争议通稿，
   标记 `consumed=True` 并裁剪 12 tick 前的旧条目，防刷屏。
   - 同 tick 新写入的话题留到下一 tick 处理，避免与即时争议重复。
3. **表达层注脚**：负奖人物写入"notorious（翻车）"长期记忆，媒体渲染时在背景注脚带出
   "曾因最差表演被金酸梅点名"，丰富文本而不参与任何判定（遵守 §11）。

### 14.4 验证
- `test_negative_awards.py`：枚举取值、badness 单调性、高开低走惩罚、分类路由、尖锐 fact_pack/媒体挑选，全绿。
- `verify_imports.py`：新增 `award_award_type_col` / `category_award_type_col` / `award_type_enum_values` 校验。
- 端到端（需本地 PG）：见 `LOCAL_GUIDE.md` §6.8 —— 创建负奖、推进跨年、查看 `news` 中 `news_type=controversy` 与 `sharp_topics` 记忆。


## 16. Phase 6（一）用户角色体系：身份模型与角色边界

> 移动端适配（无状态 + CORS）已在 v0.9 作为基础设施就绪（API_CONTRACT.md）。本阶段在其上叠加
> **身份/权限层**，仍严格保持无状态（服务端不保存会话，玩家身份由 per-request Bearer 令牌解析）。

### 16.1 身份类别（PlayerRole）

| 角色 | 核心能力 | 关键边界 |
|---|---|---|
| `audience` 观众 | 观察/游玩、推进模拟、观众打分 | 不可干预世界、不可创建奖项/写正式评论 |
| `critic` 影评人 | 在 `critic_domains` 内写正式评论、创建奖项 | 不可干预世界、不可管理玩家；奖项创建受领域限定 |
| `investor` 投资人 | 为作品融资/投资 | 不可写评论、不可创建奖项、不可干预世界 |
| `gm` 上帝模式 | 全权限：干预世界（留痕 `interventions`）、生成实体、管理玩家 | 无额外限制 |

- 影评人通过 `critic_domains`（WorkDomain 子集，如 `["film","tv"]`）成为"剧评人/音乐评论人"，
  与 §15 多领域奖项正交；`critic_can_create_award(role, critic_domains, domain)` 做领域闸门。
- 观众打分影响 `audience_score` 确定性噪声项（§11 表达层之外不改变判定链）；影评人评论进入
  媒体 Agent 的 `review` 新闻（后续 Phase 6 步骤落地）。

### 16.2 数据模型（迁移 `0007_player_roles`，新增表、向后兼容）

```
players:
  id, world_id(FK, 索引), name, role(player_role 枚举, 默认 audience),
  player_key(String(64), 唯一索引, 服务端一次性生成), critic_domains(jsonb, 可空),
  bio(Text, 可空), is_active(Boolean, 默认 true), created_at, updated_at
```
- `player_key` 即 Bearer 令牌秘密（64 位十六进制，由 `secrets.token_hex(32)` 生成），
  **服务端不下发后不可反推**；客户端（App/H5）负责持有。
- 新增 `player_role` 枚举；**不改动任何既有表/列**。

### 16.3 权限矩阵（声明式，`app/auth/roles.py`）

```
PERM_WORLD_READ       读取世界/时间线/事件/新闻/角色/作品/奖项/报告
PERM_SIM_ADVANCE      推进模拟 tick
PERM_RATING_WRITE     观众打分
PERM_REVIEW_WRITE     影评人正式评论 → 媒体 review 新闻
PERM_AWARD_CREATE     创建奖项/奖季（critic 按 domain 受限，gm 全开）
PERM_PROJECT_INVEST   投资/融资
PERM_ENTITY_CREATE    直接生成世界内实体（≡ InterventionType.CREATE）
PERM_WORLD_INTERVENE  上帝模式干预（留痕 interventions）
PERM_PLAYER_ADMIN     玩家管理（停用/启用/改角色）
```
- `ROLE_PERMISSIONS: role → {perms}`；GM 为全权限超集。
- `WRITE_PERMISSIONS`：所有写类权限在 `require_permission` 工厂内触发 423 只读锁校验（与
  `require_writable_world` 对齐），保证"只读存档不可被任何角色改写"。
- 校验确定性、请求级、可重放，**不影响 tick 可重放性**（§11）。

### 16.4 无状态令牌解析与依赖（`app/api/deps.py`）

```
_resolve_player(world_id, authorization, db):
    Bearer 方案? → player_key 查询 → 启用态? → player.world_id == world_id?
    任一失败返回 None（视为未授权）
get_player_optional(...)  → 可选身份（只读/匿名场景）
get_player(...)           → 必需身份，缺失/无效 → 401
require_permission(perm)  → 依赖工厂：解析玩家 + 角色校验；
                            写类权限先经 423；无权 → 403；无令牌 → 401
```
- **跨世界隔离**：即使令牌合法，若 `player.world_id != 路径 world_id`，本世界视为未授权。
- 用法示例（GM 专属）：`gm: Player = Depends(require_permission(PERM_PLAYER_ADMIN))`。

### 16.5 玩家路由（`app/api/players.py`，`/worlds/{world_id}/players`）

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| POST | `/` | 公开（GM 自举/授权边界） | 创建玩家，一次性下发 `player_key`；`role` 非法→422；critic 缺 `critic_domains`→422；首个 GM 可自举，其后 GM 须既有 GM 令牌授权（403） |
| GET | `/` | 公开 | 列出本世界玩家 |
| GET | `/me` | Bearer 必需 | 当前令牌身份（App/H5 能力探测） |
| GET | `/{player_id}` | 公开 | 单玩家信息 |
| POST | `/{player_id}/deactivate` | GM | 停用玩家 |
| POST | `/{player_id}/activate` | GM | 启用玩家 |

### 16.6 验证

- `verify_imports.py`：新增 `player_table_cols` / `player_role_enum_values` / `gm_is_superset` /
  `audience_no_intervene` / `audience_no_award_create` / `investor_no_review` /
  `critic_no_intervene` / `critic_domain_ok` / `critic_domain_denied` / `gm_domain_any` 等全 True。
- `test_phase6_identity.py`（离线，全绿）：枚举/模型列/权限边界/影评人领域限定/
  `_resolve_player`（缺头/非 Bearer/跨世界/停用/未知密钥 → None）/ `require_permission`（401/403/423 路由）。
- `app/main.py` 已 `include_router(players.router)`，6 条路由注册成功。
- 端到端（需本地 PG）：见 `LOCAL_GUIDE.md` §6.10。

### 16.7 Phase 6（二）落地：业务动作绑定 + 玩家视角/能力接口

> 将 §16.3 的权限矩阵真正接入核心业务动作，并补完面向 App/H5 的客户端接口。

**1. 四个核心动作的权限网关（全部接入 `require_permission`，无状态、请求级、可重放）**

| 业务动作 | 端点 | 网关权限 | 关键约束 |
|---|---|---|---|
| 推进时间 | `POST /sim/advance` | `PERM_SIM_ADVANCE` | 任何已认证角色可推进；只读存档经 `require_writable_world` 返 423 |
| 上帝干预（审计归因） | `awards.override_winner` / `festivals.override_award` | `PERM_WORLD_INTERVENE` | `Intervention.user_id = str(player.id)`——原本默认 `'god'`，现已归因到具体 GM 玩家 |
| 奖项闸门 | `awards.create_award` / `create_category` | `PERM_AWARD_CREATE` | `critic_can_create_award()` 领域闸门：影评人越界（domain ∉ critic_domains）返 403 |
| 项目融资 | `POST /projects/{id}/financing`（新增） | `PERM_PROJECT_INVEST` | 仅 investor/gm；记录 `Intervention(FINANCING, user_id=player.id)`，状态迁 `FINANCING`、`quality_metrics` 累加 `financing_total`/`financings` |

- 新增 `InterventionType.FINANCING`（迁移 `0008_intervention_financing`：`ALTER TYPE intervention_type ADD VALUE 'financing'`，向后兼容、不新增表）。
- **设计修正**：`PERM_PLAYER_ADMIN` 不纳入 `WRITE_PERMISSIONS`——玩家管理属账号级操作，与"世界内容冻结(423)"无关，故即使存档只读，GM 仍可停用/启用玩家。

**2. 面向客户端的玩家视角与角色能力接口（`app/api/players.py`）**

- `GET /me` → `PlayerMeOut`：身份 + `capabilities`（权限串）+ `actions`（客户端可渲染动作列表），供 App/H5 动态渲染按钮。
- `GET /me/portal` → `PlayerPortalOut`：**单次调用即首页所需全部数据**——玩家身份 + 能力集 + 世界快照（名称/年月/行业景气/状态/总 tick）+ 近期时间线（本世界最近 20 条事件）。无状态、请求级解析。
- 客户端动作目录 `ACTION_CATALOG`（`app/auth/roles.py`）+ `capabilities_of(role)`：集中定义"角色→可见动作"，新增动作只改一处即同步到权限矩阵、/me、/portal。

**3. 验证**

- `verify_imports.py`：新增 Phase 6（二）校验（`action_catalog_nonempty` / `gm_sees_all_actions` / `player_me_out_import` / `financing_enum_value` / `project_invest_is_write_perm` / `player_admin_not_world_write` 等全 True）。
- `test_phase6_actions.py`（离线，13 项全绿）：动作目录完整性 / 四动作网关 401·403·423 路由 / `PlayerMeOut`·`PlayerPortalOut` 装配 / 融资 Schema 与 FINANCING 枚举。
- 与既有 39 项单测合计 **52 项全绿**。端到端（需本地 PG）：见 `LOCAL_GUIDE.md` §6.11。

### 16.8 后续演进路线（社会与商业生态链）

Phase 6 基础能力（身份/权限/玩家视角）已就位。让娱乐圈更真实立体的三大生态链规划见 **§17**（属于 Phase 后续扩展，不在 Phase 6 必交付内）。

### 16.9 生产加固（备注）

GM 创建当前为"首 GM 自举 + 后续授权"的沙箱策略；生产须叠加外部鉴权（签名头/OAuth2/OIDC），
本框架保持无状态、仅做角色边界判定。`player_key` 为一次性下发的 Bearer 秘密，服务端不存会话。

---



## 17. 后续演进路线：社会与商业生态链（让娱乐圈更真实立体）

> 愿景级规划（非 Phase 6 必交付）。目标：在既有"确定性模拟 + 多 Agent + 因果可解释 + 无状态 API"
> 骨架上，补完让世界"活起来"的社会与商业生态。**所有新增机制必须复用既有基础设施**：
> ① 评分/概率走确定性算法（§11，禁止纯随机）；② 争议类内容复用
> "负面奖项 → `sharp_topics` → 媒体 Agent 争议通稿"闭环（§14）；③ 玩家干预复用 `Intervention` 审计；
> ④ tick 可重放（rng_seed 固定）。

### 17.1 商业价值与时尚资源

> **状态：已落地实现（2026-08-16）**。底层逻辑（品牌代言 · 杂志封面 · 塌房违约金）全部确定性、可重放，
> 并**与 §17.3 塌房强耦合**：丑闻塌房（COLLAPSED）瞬间自动触发 `apply_collapse_penalty`，
> 把"黑料/塌房（§17.3）"和"真金白银的商业帝国（§17.1）"焊死在"商业—舆论—资本"闭环。

#### 17.1.1 数据模型（迁移 `0010_commercial`，纯新增、向后兼容）
- 枚举：`endorsement_tier`(top_luxury/high_luxury/mass/brand_friend)、
  `contract_status`(active/terminated/breached/expired，代言与封面共用)、
  `magazine_tier`(top5/second_tier)。
- `endorsements`：world_id / character_id / brand_name / category / tier / **annual_fee(万/年)** /
  **penalty_rate(0-1 违约金比例)** / has_morals_clause(道德条款) / signed_tick / duration_ticks /
  status / terminated_tick / **penalty_amount(实赔违约金)**。
- `magazine_covers`：world_id / character_id / magazine_name / tier / issue_tick / theme / fee /
  prestige / status(active/terminated) / cancelled_tick。
- `characters.commercial_value`（Numeric，可空）：人物商业价值指数；**同时镜像进 `attributes`**
  供市场 Agent 读取（既有读取零改动）。

#### 17.1.2 商业价值与自动商务（确定性、可重放）
- 人物 `commercial_value` 由代言/封面贡献；每 tick `CommercialAgent` 为高热度艺人（`attributes.heat`
  作人气代理，与 character_agent/market_agent 同源口径）**确定性地**接洽代言/封面：
  - 倾向 `propensity = (heat − 层级门槛) + ((id + tick_index + 序号) % N) − 基线`，≥阈值才签，
    **绝不随机**；同一艺人同时生效代言≤3、封面≤2（cap 限流）；
  - 塌房人物（`Scandal` 有 COLLAPSED）不再接新商务。
- 品牌/杂志为确定性目录（`BRAND_CATALOG` / `MAGAZINE_CATALOG`），层级决定代言费基准与塌房贬值权重。

#### 17.1.3 塌房违约金（与 §17.3 的焊点）
当 §17.3 `CrisisAgent` 把丑闻推入 `COLLAPSED`，立即调用 `apply_collapse_penalty`（§17.1）：
1. 遍历该人物**带道德条款的生效代言** → 状态 `breached`，违约金 =
   `annual_fee × penalty_rate × 剩余年限占比`（封顶全剩余）；
2. 商业价值按严重度重挫：`new = old × (1 − (0.6 + 0.03×severity))`（severity=9 → 贬值约 87%）；
3. 未刊登封面 → `terminated`（取消）；
4. 写「商业塌房」事件 + **§14 复用**：`sharp_topics`(domain=commerce) → 媒体 Agent 下一 tick
   自动生成争议通稿（媒体 Agent 零改动）；另写 `char:{id}:commercial` 长期记忆。

#### 17.1.4 玩家接口（commerce:manage 网关 + Intervention 审计）
- `GET /worlds/{wid}/commerce/endorsements`、`GET .../covers`、`GET .../characters/{cid}/summary`（商业概览）；
- `POST .../endorsements`（GM 签代言）、`POST .../endorsements/{id}/terminate`（协商解约/标记违约）、
  `POST .../covers`（安排封面）；均经 `commerce:manage` 网关，落 `Intervention` 审计，只读存档返 423。
- 塌房违约金为系统自动结算（不经此路由），保证"塌房即赔"不可逆。

#### 17.1.5 三角色视角（沿用 §16 能力接口）
- 观众/影评人：吃瓜、看商业崩塌新闻；投资人：评估塌房对融资回撤（§17.1 违约金联动的未来触点）；
  GM/运营：经 `commerce:manage` 签约/解约/安排封面并留痕。
- 客户端 `ACTION_CATALOG` 新增 `commerce:manage`（"商业时尚与代言管理"），App/H5 据角色动态渲染。

### 17.2 人际关系与情感网络（人生档案馆）

> **状态：已落地实现（2026-08-16）**。底层逻辑（恋情/绯闻/婚育编排 · 粉丝应援/脱粉回踩蝴蝶效应 · 与 §17.3 出轨拆散桥接）全部确定性、可重放；并新增「人生档案馆」只读聚合接口。三大生态链最后一块拼图补全。

#### 17.2.1 数据模型（迁移 `0011_relationship`，纯新增、向后兼容）
- 新建枚举 `romance_type`(dating/rumor/married/cohabit) 与 `romance_status`(active/ended)；
- 新建表 `romances`(world_id/character_a_id/character_b_id/romance_type/status/is_public/publicness/reacted_tick/child_count/started_tick/ended_tick/ended_reason)；
- **人生档案馆为只读聚合接口，不新建任何表**（从 awards/endorsements/scandals/romances/career_history/events/长期记忆 结构化留痕）。

#### 17.2.2 粉丝蝴蝶效应（确定性、可重放，`RomanceAgent` 每 tick 调度）
- **粉丝画像 `fan_profile`**：依人物类型（歌手/演员/音乐人…）给出「偶像依赖度 idol_appeal」（歌手最高，依赖单身/CP 红利；成熟型艺人低），亦可经 `attributes.idol_appeal` 覆盖（如刻意经营"少女偶像"人设）。
- **`compute_fan_reaction`（纯函数）**：关系公开瞬间按 `偶像依赖度` 确定性结算
  `脱粉(solo_defect) vs 应援(cp_support)`：
  - 偶像型艺人公开恋情/结婚/生子 → 单人粉梦碎**大幅脱粉**，且 `idol_appeal≥70` 时触发**回踩**（口碑额外下滑）；
  - 成熟型艺人 → 影响温和，甚至小幅应援（婚礼/新生儿常被祝福）；
  - **绯闻未坐实** → 仅制造话题热度（吃瓜围观），不脱粉；实锤后按恋情处理。
- 结算落到双方 `attributes.heat`（钳制 [0,100]）+ `CharacterAttributeLog` 留痕；并**镜像贬值商业价值**（与 §17.1 同源口径）。

#### 17.2.3 与 §17.3 强耦合（出轨拆散）
- 每 tick 演化时，`RomanceAgent` 读取 §17.3 的 `Scandal`：若任一方卷入**出轨(affair)** 丑闻
  （SPREADING/ERUPTED/COLLAPSED），本关系自动结束（分手/离婚），出轨方额外脱粉——
  「黑料(§17.3) → 情感崩塌(§17.2)」，**零改动 CrisisAgent**。

#### 17.2.4 无缝复用 §14 闭环（媒体 Agent 零改动）
- 公开恋情 / 回踩 / 因丑闻分手 均写「情感争议」事件（媒体当 tick 生成 CONTROVERSY 新闻）
  + 世界记忆 `sharp_topics`(domain=relationship)，媒体 Agent 下一 tick 自动生成争议通稿。

#### 17.2.5 人生档案馆（LifeArchive，只读聚合）
- `GET /worlds/{world_id}/characters/{character_id}/archive` 结构化返回：
  基础属性、`award_summary`（获奖/提名计数+成就注脚）、`awards`(历年奖项)、`commercial`(历年代言/封面)、
  `scandals`(丑闻)、`relationships`(情感变迁与子女)、`career_history`、`major_events`、`timeline`(合并排序时间轴)；
- **重大历史事件随岁月沉淀动态渲染**：`legacy_footnotes` 直接读取人物长期记忆
  （`char:{id}:notorious` 塌房注脚 / `char:{id}:commercial` 商业崩塌 / `char:{id}:honor` 奖项荣誉），
  记忆随 tick 沉淀，故同一人物在不同时点的档案馆呈现会动态变化（如塌房后自动带出"曾因丑闻塌房"）。

#### 17.2.6 玩家接口（relationship:manage 网关 + Intervention 审计）
- 路由 `app/api/romance.py`（前缀 `/worlds/{world_id}`）：
  `GET /relationships`（列表）、`POST /relationships`（编排，relationship:manage + Intervention(CREATE)）、
  `POST /relationships/{id}/reveal`（官宣公开，即时结算蝴蝶效应）、
  `POST /relationships/{id}/add-child`（生子，已公开则触发「新生儿」反应）、
  `POST /relationships/{id}/end`（结束）、`GET /characters/{id}/archive`（人生档案馆，仅需 world:read）。
- `roles.py` 新增 `PERM_RELATIONSHIP_MANAGE`(GM，写类) 与 `ACTION_CATALOG` 条目；App/H5 据角色动态渲染"情感网络编排"按钮。

### 17.3 舆论与危机公关

> **状态：已落地实现（2026-08-16）**。底层逻辑（黑料爆料 · 丑闻演化 · 多阶段公关）全部确定性、可重放，
> 并**无缝复用 §14 的「负面奖项 → sharp_topics → 媒体争议通稿」闭环**（媒体 Agent 零改动）。

#### 17.3.1 数据模型（迁移 `0009_scandal_crisis`，纯新增、向后兼容）
- 枚举：`scandal_type`(affair/drugs/tax/slip_of_tongue/surrogacy/plagiarism/domestic_violence/other)、
  `scandal_stage`(latent/spreading/erupted/resolving/resolved/collapsed)、`pr_strategy`(cold_treatment/
  lawyer_letter/apology/buy_trending/counter_mkt)。
- `scandals`：world_id / character_id / related_project_id / scandal_type / title / severity(1-10) /
  evidence_strength(1-10) / is_confirmed / stage / **heat(0-100 热度)** / **public_opinion(0-100 舆情分，
  复用 media_score 口径方向，50=中性)** / exposed_tick / erupted_tick / resolved_tick / created_by / notes。
- `crisis_pr`：scandal_id / strategy / by_player_id / **impact(JSONB，确定性结算结果，可审计)** / note。
- `intervention_type` 扩展 `'scandal'` / `'crisis_pr'`，使舆论干预经 `Interventions` 审计（与 §16 一致）。

#### 17.3.2 黑料爆料（玩家经 crisis:manage 网关，留痕 Intervention）
- `POST /worlds/{world_id}/scandals`：创建丑闻；`exposed=true`→立即 `SPREADING`，否则先 `LATENT`(潜伏)。
- `POST /worlds/{world_id}/scandals/{id}/expose`：曝光潜伏丑闻（LATENT→SPREADING）。
- 权限矩阵：`PERM_CRISIS_MANAGE` 仅授予 GM（运营角色可在 §16.3 扩展）；属写类权限，只读存档返 423。

#### 17.3.3 丑闻演化（确定性状态机，`CrisisAgent` 每 tick 调度，位于媒体 Agent 之前）
```
LATENT ──expose──▶ SPREADING ──(≥2 tick 发酵)──▶ ERUPTED
                                          │
                              (公关动作) ──▶ RESOLVING ──(热度归零并稳定 3 tick)──▶ RESOLVED
                                          │
              (实锤+严重(sev≥8)+口碑≤5) ───────────────────────────────────────────▶ COLLAPSED(塌房,不可逆)
```
- 热度每 tick 乘性衰减（`×0.85-1`）；SPREADING 缓升热度、缓降口碑；ERUPTED 口碑持续下滑。
- 爆发瞬间口碑重创 `drop = severity×2 + evidence + (12 if 实锤)`（封顶 60）。
- 平静（heat≤25）后口碑按恢复曲线回归基线 `max(8, 50 - severity×2)`（越严重越难完全恢复）。

#### 17.3.4 多阶段公关（确定性"舆论恢复曲线"，`evaluate_pr` 纯函数）
动作 × 严重度 × 证据强度 × 是否实锤 → 确定性结算（delta_heat / delta_opinion / 可解释说明）：
| 公关动作 | 证据弱(诬陷) | 已实锤 | 关键胜负手 |
|---|---|---|---|
| 冷处理 | 热度降、口碑持平 | 仍装死→公众不满(略负) | 不回应，靠时间冷却 |
| 发律师函 | 维权成功(+口碑) | 像"捂嘴"→反感(负) | 证据弱时奏效 |
| 公开道歉 | 变相认锤(负) | 认错被接受(+) | **实锤才该道歉** |
| 买热搜 | 短期压热度、口碑略负、随后反弹 | 强行洗地(负) | 仅烟雾弹 |
| 反向营销/洗白 | **大翻盘(+)** | 遭群嘲(塌房加速,负) | **证据弱才能洗白** |

- `POST /worlds/{world_id}/scandals/{id}/pr`：发起公关，写 `crisis_pr`(含 impact 结算) + `Intervention(crisis_pr)`，
  丑闻转入 `RESOLVING`；`GET /.../{id}/pr` 查历史。

#### 17.3.5 无缝复用 §14 闭环（媒体 Agent 零改动）
1. **爆发/关键节点**产「丑闻争议」事件（category 含"争议"）→ 媒体 Agent `_classify_news_type` 路由为 `CONTROVERSY` 新闻（与负面奖项同源路径）。
2. **sharp_topics 复用**：`CrisisAgent` 把丑闻话题写入世界记忆 `sharp_topics`（同 schema，domain="crisis"），
   媒体 Agent **下一 tick** 自动消费并生成争议通稿（本 tick 新写入留到下一 tick，与 §14.3 完全一致）。
3. **notorious 注脚复用**：塌房/平息写入 `char:{id}:notorious` 长期记忆 → §14.3 媒体背景注脚自然带出"曾因丑闻塌房"。
4. **_badness 桥接**：`scandal_reputation_penalty()` 把"已曝光+实锤"丑闻的劣迹加成喂入 `AwardAgent._badness`，
   使丑闻缠身者在负奖（金酸梅）中更易被点名（见 §14.2 的负奖判定扩展）。

#### 17.3.6 三角色视角（沿用 §16 能力接口）
- 观众：吃瓜、打分（`PERM_RATING_WRITE`）；影评人：评论发酵（`PERM_REVIEW_WRITE`）；
- 投资人：评估塌房对融资回撤（§17.1 违约金联动的未来触点）；GM/运营：经 `crisis:manage` 爆料/公关并留痕。
- 客户端 `ACTION_CATALOG` 新增 `crisis:manage`（"舆论与危机公关"）动作，App/H5 可据角色动态渲染按钮。

### 17.4 落地原则（与既有架构一致）

- 新增实体一律带 `world_id`、可多存档隔离；只读存档写操作 423。
- 评分/概率/概率性叙事均走确定性算法 + RNG 有界噪声（§11），tick 可重放。
- LLM 仅在表达层渲染（fact_pack → 新闻/通稿），不决定任何数值或状态转移。
- 玩家干预全部经 `Intervention` 审计；新增"运营/经纪人"等角色可在 Phase 6 权限矩阵（§16.3）扩展。
- App/H5 对接沿用 `API_CONTRACT.md` 无状态契约 + `/me/portal` 聚合接口模式。

---



