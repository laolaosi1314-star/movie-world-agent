# 影视世界 Agent · 前端（App / H5）

基于真实后端 API 契约（`API_CONTRACT.md`、各 `app/schemas/*`）的 React + Vite 前端。
对接的是**无状态 JSON API**：每个请求自带 `world_id` 路径参数 + `Authorization: Bearer <player_key>`。

## 技术栈

- React 18 + TypeScript
- Vite 5（开发服务器 / 生产构建）
- react-router-dom 6（页面路由）
- Capacitor（同一套代码一键出 iOS / Android App，见「跨端」）

> 调研规划文档：`FRONTEND_PLAN.md`。本脚手架已落地其 Phase A（基建 + 人物档案馆 + GM 工作台）。

## 快速开始

```bash
cd movie_world_agent/frontend
cp .env.example .env          # 默认指向 http://localhost:8000
npm install
npm run dev                   # 打开 http://localhost:5173
```

启动后两种进入方式：

1. **免后端 · 进入演示**：用前端内置 mock 数据，直接体验人生档案馆、时间轴、岁月沉淀注脚。
2. **创建 GM 玩家并进入**：需先在本机起好后端
   （`cd movie_world_agent && alembic upgrade head && uvicorn app.main:app --port 8000`），
   再填世界 ID（默认 1）+ 名称，点「创建 GM 玩家」。

## 页面与组件

| 页面 / 组件 | 对接接口 | 说明 |
|---|---|---|
| `pages/Login` | `POST /worlds/{id}/players` | 自举 GM / 进入演示 |
| `pages/Portal` | `GET /players/me/portal` | 首页一次调用拿齐身份+世界快照+近 20 事件 |
| `pages/CharacterArchive` | `GET /characters/{id}/archive` | 人生档案馆：商业价值断崖 + 时间轴 + 岁月沉淀注脚 |
| `pages/WorldControl` | `relationships*` / `scandals*` / `sim/advance` | GM 工作台：编排恋情、引爆塌房、推进时间 |
| `components/RoleGate` | `/me` 的 `actions` | 数据驱动按钮可见性（演示/令牌即放行） |
| `components/CommercialValueMeter` | `archive.commercial_value` | 商业价值断崖条 |
| `components/LifeArchiveTimeline` | `archive.timeline` | 一生时间轴（scandal/award/recovery 节点色） |
| `components/LegacyFootnoteCard` | `archive.legacy_footnotes` | 岁月沉淀注脚（读长期记忆，动态渲染） |
| `components/TickAdvanceFab` | `POST /sim/advance` | 浮动推进时间按钮 |

## 环境变量

- `VITE_API_BASE`：后端基址（默认 `http://localhost:8000`）。
- `VITE_USE_MOCK`：`true` 时全量走 mock（无需后端）。也可在登录页点「免后端 · 进入演示」。

## 跨端（App）

```bash
npm install @capacitor/core @capacitor/cli
npm run build                 # 产出 dist/
npx cap init 影视世界 com.movieworld.agent --web-dir dist
npm run cap:android          # 或 cap:ios
```

Capacitor 配置见 `capacitor.config.ts`，`webDir: "dist"`。

## 与后端契约对齐的注意点

- 错误码语义遵循 `API_CONTRACT.md §3`：`401` 引导登录、`403` 提示无权限、`423` 提示只读存档。
- 多世界隔离：`world_id` 路径参数 + 服务端按世界解析令牌；前端本地持久持有 `world_id` 与 `player_key`。
- 所有写操作（情感编排 / 丑闻 / 推进）在**只读存档**上由后端返回 `423`，前端仅需友好提示，无需自管锁状态。

## 下一步（规划见 FRONTEND_PLAN.md）

- 接入 TanStack Query（天然按 `world_id` 缓存隔离）与 Zustand（本地 UI 状态）。
- 真实 `player.capabilities` 门控（替代当前演示态放行）。
- 分页 / 实时推送（SSE）/ 头像与多领域奖项展示 / 国际化。
