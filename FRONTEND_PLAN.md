# 前端接入调研：App / H5 视觉界面研发

> 阶段定位：后端核心逻辑已封包（**89 项单测全绿**，`§17.1 商业时尚`·`§17.2 人际情感`·`§17.3 舆论危机`三大生态链闭环，无状态 JSON API）。
> 本文档基于已沉淀的 `API_CONTRACT.md`、`/me/portal`、`/characters/{id}/archive` 接口，正式开启 App/H5 视觉界面研发阶段的调研与规划。
> 目标：给前端团队一份**可直接开工**的接入蓝图——接口面、数据模型、技术栈、页面/组件拆分、鉴权与 Mock 策略、分阶段计划。

---

## 1. 调研结论（TL;DR）

1. **后端已为前端铺好"聚合入口"**：`GET /players/me/portal` 一次调用返回首页全部数据（身份 + 能力 + 世界快照 + 近 20 条事件）；`GET /characters/{id}/archive` 一次返回某艺人完整人生档案与时间轴。前端**首页与人物页几乎零聚合成本**。
2. **无状态契约天然适配 SPA/移动端**：每请求带 `Authorization: Bearer <player_key>` + 路径 `world_id`；服务端不存会话。客户端是状态唯一持有者（持有 `world_id`/`player_key`/本地缓存）。
3. **角色门控可纯数据驱动**：`/me` 返回 `actions[]`（含 `key`/`label`/`permission`/`requires_world_writable`），前端按 `actions` 决定按钮显隐，**无需硬编码角色分支**。
4. **推荐栈**：React 为核心（与团队 TypeScript 心智一致）；H5 用 Vite + React Router；App 用 **Capacitor** 包裹同一套 React（iOS/Android 一套代码）；数据层 **TanStack Query**（缓存/重试/轮询）+ **Zustand**（持有 `player_key`/`world_id`）。

---

## 2. 资产盘点（后端已就绪）

| 资产 | 位置 | 前端用途 |
|---|---|---|
| 统一错误码语义 | `API_CONTRACT.md §3` | 401/403/422/423 直接分支 |
| 多世界租户键 | `API_CONTRACT.md §2` | 所有路由 `/worlds/{world_id}/...`，客户端持有 `world_id` |
| CORS 配置 | `API_CONTRACT.md §5` | H5 跨域：`CORS_ALLOW_ORIGINS` 白名单 |
| 玩家视角聚合 | `GET /players/me/portal` | **首页唯一数据源** |
| 身份 + 能力集 | `GET /players/me` | 角色门控、按钮渲染 |
| 人生档案馆 | `GET /characters/{id}/archive` | **人物页核心**：档案 + 时间轴 + 岁月沉淀注脚 |
| 权限矩阵 | `BLUEPRINT.md §16` / `API_CONTRACT.md §7.3` | 与 `actions[]` 对齐，前端不重复定义 |
| 三大生态链接口 | §17.1/§17.2/§17.3 路由 | GM 工作台（编排/危机/商业） |

---

## 3. 可用接口面（面向前端，按领域）

> 权限标注：`R`=world:read 即可（任意已授权玩家）；`W:xxx`=需 `xxx` 写权限（GM/运营）；`423`=只读存档写操作被拒。

| 领域 | 方法 & 路径 | 权限 | 前端用途 |
|---|---|---|---|
| 多世界 | `GET /worlds` | R | 世界列表 |
| 多世界 | `POST /worlds` | 写 | 开新档 |
| 多世界 | `GET /worlds/{id}` | R | 世界详情 |
| 多世界 | `POST /worlds/{id}/archive` | W | 转只读存档（423 保护） |
| 身份 | `POST /worlds/{id}/players` | — | 创建玩家并下发 `player_key`（GM 首建自举） |
| 身份 | `GET /players/me` | 令牌 | 当前身份 + `actions[]` |
| 身份 | `GET /players/me/portal` | 令牌 | **首页聚合** |
| 人物 | `GET /worlds/{id}/characters` | R | 人物列表 |
| 人物 | `POST /worlds/{id}/characters` | W | 创建人物 |
| 关系(§17.2) | `GET /worlds/{id}/relationships` | R | 关系列表 |
| 关系(§17.2) | `POST /worlds/{id}/relationships` | W:relationship | 编排恋情/绯闻/婚育 |
| 关系(§17.2) | `POST /relationships/{rid}/reveal\|add-child\|end` | W:relationship | 官宣/生子/结束 |
| 档案馆 | `GET /characters/{cid}/archive` | R | **人生档案馆** |
| 危机(§17.3) | `GET /worlds/{id}/scandals` | R | 丑闻列表 |
| 危机(§17.3) | `POST /worlds/{id}/scandals` | W:crisis | 黑料爆料 |
| 危机(§17.3) | `POST /scandals/{sid}/expose\|pr` | W:crisis | 曝光/多阶段公关 |
| 商业(§17.1) | `GET /commerce/endorsements\|covers` | R | 代言/封面列表 |
| 商业(§17.1) | `POST /commerce/endorsements` | W:commerce | 签代言 |
| 商业(§17.1) | `GET /commerce/characters/{cid}/summary` | R | 商业价值/违约金概览 |
| 时间推进 | `POST /worlds/{id}/sim/advance` | W:sim | 推进 tick（任何角色） |
| 媒体 | `GET /worlds/{id}/news` | R | CONTROVERSY 等新闻流 |
| 事件 | `GET /worlds/{id}/events` | R | 时间线（portal 已含近 20 条） |

**前端只读视图（观众/投资人最常见）只需：`/me/portal` + `/characters/{cid}/archive` + `/scandals` + `/commerce/.../summary` + `/news`**，全部 `world:read`，无需写权限。

---

## 4. 关键数据模型（前端 TS 类型定义来源）

直接映射自 `app/schemas/*` 的 Pydantic 模型：

- **PlayerPortalOut** `{ player: PlayerMeOut; world: {id,name,current_year,current_month,industry_status,status,total_ticks}; recent_events: EventOut[] }`
- **PlayerMeOut** = PlayerOut + `capabilities: string[]` + `actions: {key,label,permission,requires_world_writable}[]`
- **LifeArchiveOut**
  ```ts
  interface LifeArchiveOut {
    character_id; name; type; birth_year?; career_stage; status; heat;
    commercial_value?: number;
    award_summary: Record<string, any>; awards: any[];
    commercial: any[]; scandals: any[]; relationships: any[];
    career_history: any[]; major_events: any[];
    timeline: { year?; kind; title; detail?; significance }[];
    legacy_footnotes: any[];   // ← 岁月沉淀注脚（塌房/商业崩塌/荣誉，随年份动态带出）
  }
  ```
- **EndorsementOut / MagazineCoverOut / CommercialSummary** / **ScandalOut / CrisisPROut** / **RomanceOut** —— 见各自 schema。

> 建议：用 `openapi.json`（`uvicorn` 启动后访问 `/openapi.json`）生成 TypeScript 客户端（`openapi-typescript` / `orval`），与后端契约保持强一致，避免手工维护类型漂移。

---

## 5. 推荐技术栈（App + H5 跨端）

| 层 | 选型 | 理由 |
|---|---|---|
| 框架 | **React 18 + TypeScript** | 团队心智统一；H5/App 复用同一业务层 |
| 构建 | **Vite** | 快；H5 直出，App 由 Capacitor 包裹 |
| 路由 | React Router v6 | 嵌套路由契合 `world/:id/character/:cid` |
| 数据 | **TanStack Query v5** | `queryKey:['world',wid,'archive',cid]` 天然做 world 隔离缓存；`retry`/`refetchInterval` 适配 423/网络抖动 |
| 状态 | **Zustand** | 仅存 `player_key`/`world_id`/当前角色（轻量、无样板） |
| App 跨端 | **Capacitor** | 同一 React 代码打包 iOS/Android，免双端维护 |
| 样式 | Tailwind CSS + 设计令牌 | 暗/亮主题、移动优先；与后端 `IDE Theme` 无关但统一视觉 |
| 图表 | Recharts / visx | 商业价值断崖、粉丝 heat 走势、时间轴 |
| Mock | **MSW (Mock Service Worker)** | 后端未常驻时拦截契约，前端先行 |

**为什么不 vanilla / 双 Native**：后端无状态 + Bearer 令牌，SPA 原生契合；Capacitor 共享 React 业务层，研发成本最低、迭代最快。

---

## 6. 路由与页面拆分

| 路由 | 页面 | 核心接口 |
|---|---|---|
| `/login` | 登录/角色选择 | `POST /players`（拿 `player_key`；GM 自举） |
| `/worlds` | 世界列表 + 开新档 | `GET/POST /worlds` |
| `/world/:id` | **首页/聚合**（世界快照 + 近期事件流 + 能力按钮） | `GET /players/me/portal` |
| `/world/:id/character/:cid` | **人物详情 + 人生档案馆** | `GET /characters/{cid}/archive` + `/commerce/.../summary` |
| `/world/:id/relationships` | 关系编排（GM） | `GET/POST /relationships` + reveal/add-child/end |
| `/world/:id/crisis` | 危机公关（GM） | `GET/POST /scandals` + expose/pr |
| `/world/:id/commerce` | 商业编排（GM） | `GET/POST /commerce/endorsements` + summary |
| `/world/:id/news` | 媒体/争议新闻流 | `GET /news` |

**时间推进**：首页悬浮按钮 `推进一个月/季度/半年`（POST `/sim/advance`），配合乐观更新 + portal/时间线重查，呈现"世界向前走"的沉浸感。

---

## 7. 关键组件设计（视觉亮点）

- **`<RoleGate actions={...} perm="relationship:manage">`**：根据 `/me` 的 `actions` 控制 GM 工作台按钮显隐；观众/投资人看不到编排入口。**纯数据驱动，无角色硬编码**。
- **`<LifeArchiveTimeline entries={archive.timeline} />`**：竖向时间轴，按 `year` 排序；节点样式按 `kind`（award/scandal/romance/commercial/career）分色。
- **`<LegacyFootnoteCard footnote={...} />`**：`legacy_footnotes` 渲染为"岁月沉淀"特殊卡片——例如塌房后自动带出 *"曾因出轨丑闻塌房，商业帝国一夜归零"*，带淡入/做旧滤镜动画，呼应"随岁月沉淀动态渲染"。
- **`<FanReactionBadge />`**：情感公开后的脱粉/应援可视化（`heat` 红/绿箭头 + `backstab` 回踩标记）。
- **`<CommercialValueMeter />`**：商业价值仪表盘；塌房瞬间红色断崖动画（`commercial_value` 由 ~85 → 重挫至约 13%）。
- **`<WorldSnapshot />` + `<EventFeed />`**：首页聚合（`/me/portal` 的 `world` + `recent_events`）。
- **`<TickAdvanceFab />`**：悬浮推进按钮，带动效与"正在推进…"骨架屏。

---

## 8. 鉴权与令牌管理

- `player_key` 一次性下发（64 位 hex），存 **localStorage**（App 内用 Capacitor 安全存储/Capacitor Storage）。
- 每个请求带 `Authorization: Bearer <player_key>`；`world_id` 编码进 URL。
- **跨世界隔离**：令牌属于某 `world_id`，跨世界即用 401 处理 → 引导回世界列表。
- `archived` 世界写操作返回 **423** → 提示"存档只读，请克隆新档"。
- 无刷新令牌（key 长期有效），登出即清 `player_key`。

---

## 9. Mock / 联调策略（后端未常驻时）

1. **MSW 拦截**：按 §3 接口面 + schema 编写 handler，返回 `BLUEPRINT`/`API_CONTRACT` 定义的样例 JSON（含一个完整 `archive` 含 `legacy_footnotes`）。
2. **样例数据文件** `mock/world.json` / `mock/archive.json`：供 UI 走查与时间轴/注脚动画调优。
3. **真机联调**：后端按 `scripts/e2e_demo.sh` 起服务（含 `CORS_ALLOW_ORIGINS` 指向 H5 域名），前端直连 `BASE_URL` 环境变量切换 Mock/真实。

---

## 10. 分阶段研发计划

| 阶段 | 周期 | 交付 |
|---|---|---|
| **A. 基建** | ~1 周 | 脚手架（Vite+React+TS+TanStack Query+Zustand+Capacitor）；`/login`+`/worlds`+`/me/portal` 首页；`<RoleGate>` 门控；类型由 `/openapi.json` 生成 |
| **B. 人物与档案馆** | ~1 周 | 人物详情页；`<LifeArchiveTimeline>` + `<LegacyFootnoteCard>`（重点视觉：岁月沉淀动画）；`<CommercialValueMeter>`；`/commerce/.../summary` |
| **C. GM 工作台** | ~1 周 | 关系编排/危机公关/商业编排三页；`<TickAdvanceFab>` 时间推进 + 时间线流式刷新；`/news` CONTROVERSY 流 |
| **D. 跨端与联调** | ~1 周 | Capacitor 打包 iOS/Android；H5 部署；接 `e2e_demo` 后端真机/浏览器联调；亮/暗主题打磨 |

---

## 11. 待后端确认 / 补充的契约点（研发前对齐）

1. **分页上限**：列表接口已支持 `limit/offset`，前端统一封装；建议后端对 `events/news` 给出默认 `limit` 与最大页。
2. **时间线实时性**：当前 `advance` 为拉取式（推进后重查 `portal`）；是否需 **WebSocket/SSE** 推送 tick 进展？MVP 建议轮询/`refetchInterval`。
3. **`archive` 性能**：人物生涯长时 `timeline` 可能数百条；是否需 `?year=` 分段或分页？MVP 先全量（含在前端虚拟滚动）。
4. **图片/头像**：当前人物无头像字段；如需艺人立绘，建议加 `avatar_url`（不影响既有契约，向后兼容）。
5. **国际化**：契约文案为中文；前端如需多语言，建议后端字段语义稳定、展示文案放前端。

---

## 12. 小结

后端已交付一个**有生命力、确定性、可重放**的娱乐圈数字世界；前端只需"接好两个聚合入口（`/me/portal`、`/archive`）+ 用 `actions[]` 驱动门控"，即可在 4 周内产出 App+H5 双端可用产品。完整架构与表结构见 `BLUEPRINT.md`，接口字段与错误码见 `API_CONTRACT.md`，端到端验证见 `scripts/e2e_demo.sh` 与 `LOCAL_GUIDE.md §6.14`。
