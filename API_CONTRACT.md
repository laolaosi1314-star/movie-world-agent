# 影视世界 Agent — API 契约与移动端对接规范

> 适用范围：App（iOS/Android）/ H5（移动网页）/ 桌面 Web 共用同一套 JSON HTTP API。
> 本文档是「手机端适配」的**基础设施契约**（Phase 6 用户角色体系将在此基础上叠加身份/权限层），
> 与 `BLUEPRINT.md` 的 §11（LLM 仅表达层）、§15（多领域奖项）保持一致。

---

## 1. 核心原则：无状态（Stateless）

服务端**不保存任何客户端会话状态**。每个请求都自带完成处理所需的全部上下文：

| 原则 | 落地方式 | 反模式（禁止） |
|---|---|---|
| 状态外置 | 所有世界/实体状态存于 PostgreSQL，按 `world_id` 隔离 | 服务端用内存/Redis 缓存"当前登录用户当前世界" |
| 请求自包含 | `world_id` 作为**路径参数**携带于每个业务请求 | 依赖 Cookie/Session 隐式传递世界上下文 |
| 请求级资源 | DB 会话由 `Depends(get_db)` 按请求创建与释放 | 跨请求复用连接/事务对象 |
| 幂等写 | 写操作可重复发起（上帝模式留 `interventions` 审计）；无副作用累加 | 服务端累计"已发送"计数等隐式状态 |
| 只读锁 | `archived` 世界写操作统一 `423 Locked`，状态由 `world.status` 决定 | 服务端用标志位记忆"该用户是否只读" |

> 结论：**客户端（含手机端）是状态的唯一持有者**——它负责记住当前在浏览哪个 `world_id`、
> 当前 tick 进度、UI 本地缓存；服务端只认请求里的 `world_id`。

---

## 2. 多世界租户键（Tenant Key）

- 所有业务路由统一挂载在 `/worlds/{world_id}/...` 命名空间下（见 `verify_imports.py` 的
  `routes_without_world_id: none` 校验）。
- 不存在"全局默认世界"；缺失 `world_id` 即 404。
- `world_id` 即"存档/宇宙"主键，天然支持多存档与只读存档（archived→423）。

---

## 3. 统一错误码语义（供 App/H5 直接分支）

| HTTP | 含义 | 客户端处理建议 |
|---|---|---|
| `200` | 成功 | 解析 JSON |
| `201` | 资源已创建 | 读取 `Location`/响应体 id |
| `400` | 请求体格式错误 | 提示用户修正输入 |
| `404` | 资源/世界不存在 | 跳转世界列表或提示"存档已删除" |
| `422` | 参数校验失败（含非法 `domain`/`kind`/`award_type`/`role`） | 高亮对应字段，给出 `detail` 文案 |
| `423` | 只读存档，禁止写入 | 提示"该存档只读，请克隆新档" |
| `401` | 缺少或无效的玩家身份令牌 | 引导登录/创建玩家并携带 `Authorization: Bearer <player_key>` |
| `403` | 玩家角色无权执行该操作 | 提示"当前身份（如 audience）无此权限"，或引导切换 GM |
| `500` | 服务端异常 | 重试一次；仍失败则上报 |

错误响应统一结构：
```json
{ "detail": "invalid domain: 'anime' (allowed: ['film','tv','music'])" }
```

---

## 4. 分页与列表约定

- 大列表接口（`events`/`news`/`memories`）支持 `?limit=&offset=` 查询参数；
-  awards 类目/获奖列表随奖季规模增长，未来如需分页沿用同一约定；
- 列表响应为**纯数组**（非包裹信封），便于客户端 `flatMap`。

---

## 5. CORS（H5 必需）

- H5 在浏览器中跨域调用需 CORS。由环境变量 `CORS_ALLOW_ORIGINS` 控制（逗号分隔白名单）：
  ```bash
  export CORS_ALLOW_ORIGINS="https://h5.example.com,https://m.example.com"
  ```
- 未配置时默认放开 `*`（仅限本地开发）。**生产环境必须显式限定来源**。
- `allow_credentials=True` 已开启（若未来需要携带用户凭证头）。

---

## 6. 多领域奖项的接口字段（§15）

创建奖项 / 类别时新增两个正交字段：

```jsonc
POST /worlds/{world_id}/awards
{
  "name": "金唱片奖",
  "award_type": "positive",   // positive | negative
  "domain": "music",          // film | tv | music   ← 领域轴
  "positioning": "..."
}

POST /worlds/{world_id}/awards/{award_id}/categories
{
  "name": "最佳男歌手",
  "award_type": "positive",
  "domain": "music",
  "kind": "singer_male"       // 类目客体种类（§15.3 CategoryKind 全集）
}
```

`kind` 取值全集：`project` / `director` / `actor_male` / `actor_female` / `writer` /
`album` / `single` / `singer_male` / `singer_female` / `lyricist` / `composer`
（以 `WorkDomain` + `CategoryKind` 枚举为准，非法值→422）。

读取端（如 `winners`、`ceremony-review`）无需改动即可返回跨领域结果；
媒体争议闭环（sharp_topics）domain 无关，自动覆盖电视/音乐负奖。

---

## 7. Phase 6 用户角色：身份模型与无状态鉴权（已落地）

身份/权限层已叠加在 §1–§6 的无状态基础之上，**不破坏任何既有契约**。设计细节见 `BLUEPRINT.md` §16。

### 7.1 身份类别（PlayerRole）

`audience`（观众）/ `critic`（影评人，可含剧评人·音乐评论人）/ `investor`（投资人）/ `gm`（上帝模式）。
- 影评人通过 `critic_domains`（WorkDomain 子集，如 `["film","tv"]`）成为"剧评人/音乐评论人"，
  与 §15 多领域奖项正交。

### 7.2 鉴权载体（无状态、Bearer）

- 玩家身份由每个请求的 `Authorization: Bearer <player_key>` 解析；**服务端不保存会话**，
  解析后即丢弃（无 Cookie 会话）。
- `player_key` 是创建玩家时一次性下发的 64 位十六进制秘密（见 `POST /worlds/{world_id}/players`
  响应的 `player_key` 字段）；客户端（App/H5）负责持久持有。
- **跨世界隔离**：令牌合法但 `player.world_id != 路径 world_id` 时，本世界视为未授权（401）。
- 无令牌/无效令牌 → `401`；角色无权 → `403`；写类权限在只读存档上 → `423`。

### 7.3 权限矩阵（声明式）

以 `role → permission` 建模，与"只读存档锁（423）""上帝模式审计（interventions）"同层，
全部请求级、确定性、可重放。权限标识（`resource:action`）：

| 权限 | audience | critic | investor | gm |
|---|:--:|:--:|:--:|:--:|
| `world:read` 读取世界/时间线/事件/新闻/角色/作品/奖项 | ✅ | ✅ | ✅ | ✅ |
| `sim:advance` 推进模拟 tick | ✅ | ✅ | ✅ | ✅ |
| `rating:write` 观众打分 | ✅ | ✅ | ✅ | ✅ |
| `review:write` 影评人正式评论 | — | ✅ | — | ✅ |
| `award:create` 创建奖项/奖季（critic 按 domain 受限） | — | ✅* | — | ✅ |
| `project:invest` 投资/融资 | — | — | ✅ | ✅ |
| `entity:create` 直接生成世界内实体 | — | — | — | ✅ |
| `world:intervene` 上帝模式干预（留痕 interventions） | — | — | — | ✅ |
| `player:admin` 玩家管理（停用/启用/改角色） | — | — | — | ✅ |

\* `critic` 的 `award:create` 仅可在 `critic_domains` 限定的领域内创建（如剧评人可建电视类奖项，不可建音乐类）。

### 7.4 玩家视角接口（客户端聚合入口，已落地）

- `GET /worlds/{world_id}/players/me` → `PlayerMeOut`：返回当前令牌身份 + `capabilities`（权限串）
  + `actions`（客户端可渲染动作列表，含 `key`/`label`/`permission`/`requires_world_writable`）。
  **App/H5 据此动态渲染可交互按钮**——无需硬编码角色逻辑。
- `GET /worlds/{world_id}/players/me/portal` → `PlayerPortalOut`：**单次调用即首页所需全部数据**
  ——玩家身份 + 能力集 + 世界快照（名称/年月/行业景气/状态/总 tick）+ 近期时间线（本世界最近 20 条事件）。
  无状态、请求级解析；首页加载只需这一次请求 + 后续动作各自携带 `Authorization` 头。
- 客户端动作定义集中在 `app/auth/roles.py` 的 `ACTION_CATALOG` + `capabilities_of(role)`；
  新增"可交互动作"时只改此处，权限矩阵、`/me`、`/portal` 自动同步。

### 7.5 生产加固备注

当前 GM 创建为"首个 GM 自举 + 其后须既有 GM 令牌授权"的沙箱策略。生产环境应叠加外部鉴权
（签名头/OIDC），本框架保持无状态、仅做角色边界判定。

---

## 8. 客户端最低要求

- 支持 JSON 解析、HTTPS（生产）、对 422/423 的友好提示；
- 维护本地 `world_id` 与 tick 进度；列表分页消费 `limit/offset`；
- 错误以 HTTP 状态码为主、以 `detail` 文案为辅，避免依赖特定错误结构。
