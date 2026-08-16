# 影视世界 Agent · 最简落地指南（手机上把玩的 App）

> 目标：你**本地没有任何编程软件**（无 Node / 无 PostgreSQL / 无 Git 客户端），
> 也能把这个后端引擎变成一个在手机浏览器里点着玩的娱乐 App。
> 本指南给出一条"最少点击、零本地工具"的路径，所有构建/编译都由云平台在云端完成。

---

## 总览：三步走

```
① 把代码放到 GitHub（你只需开个免费账号，点几下）
        │
        ├──► ② 后端部署到 Render（免费）→ 得到一个公网网址 https://xxx.onrender.com
        │         · 自带免费 Postgres 数据库
        │         · 自动跑数据库迁移（alembic upgrade head）
        │         · 立刻能在手机上用 Swagger /docs 像点游戏一样操作
        │
        └──► ③ 前端部署到 Netlify（免费）→ 得到一个 H5 网址 https://xxx.netlify.app
                  · 云端自动 npm 构建（你本地不用装 Node）
                  · 漂亮的中文手机界面：人物档案 / 时间轴 / 危机公关 / 推进 Tick
```

> 只有 **GitHub 账号** 是绕不开的（免费、2 分钟注册）。Render 与 Netlify 都用 GitHub 登录即可。

---

## 第 ① 步：把代码送上 GitHub

工程已在 `movie_world_agent/` 下，包含后端（`app/`）+ 前端（`frontend/`）+ 部署配置（`render.yaml` / `netlify.toml`）。

**方式 A（推荐，最省事）——让我帮你推：**
1. 你到 github.com 新建一个**空仓库**（不要勾选 README/.gitignore）。
2. 生成一个 **Personal Access Token**（Settings → Developer settings → PAT，勾 `repo` 权限，过期设长一点）。
3. 把 token 和仓库地址发给我，我直接 `git push` 上去（一次性，之后你不用管）。

**方式 B（自己来，无需本地 Git）：**
1. 在 github.com 新建仓库。
2. 用 **GitHub Desktop**（桌面客户端，官网下载，图形界面，无需命令行）或网页端 "Add file" 把 `movie_world_agent/` 整个文件夹传上去。

> 不论哪种方式，仓库里**必须包含**这些文件（都已就绪）：
> `requirements.txt`、`runtime.txt`、`render.yaml`、`alembic.ini`、`app/`、`frontend/`、`netlify.toml`。

---

## 第 ② 步：后端免费部署到 Render（得到公网网址）

1. 打开 https://render.com ，用 **GitHub 登录**。
2. 右上角 **New + → Blueprint**（不是 "Web Service"）。
3. 选择你的仓库 → Render 会**自动读取 `render.yaml`**，预览出：
   - 一个 `movie-world-agent` Web 服务（免费档）
   - 一个 `movie-world-db` Postgres（免费档，自动注入 `DATABASE_URL`）
4. 点 **Apply**，坐等 2~3 分钟构建。完成后你会得到一个网址，例如：
   ```
   https://movie-world-agent.onrender.com
   ```
5. 验证：手机/电脑浏览器打开 `https://<你的网址>/health` → 应返回 `{"status":"ok"}`。

**关键机制（已为你写好，无需改动）：**
- `render.yaml` 的 `releaseCommand: alembic upgrade head` → 每次部署自动建表/升库（含 §17.2 的 `romances` 表）。
- `startCommand` 用 `$PORT` 监听，满足云平台端口要求。
- `CORS_ALLOW_ORIGINS=*` → 允许 H5 网页跨域调用。上线后可改成你的 Netlify 域名。

> ⚠️ 免费档**闲置会休眠**：超过约 15 分钟无访问，下次打开需等 ~30 秒冷启动。个人把玩完全够用。

---

## 第 ③ 步：手机上怎么玩（两种方式，任选）

### 方式一：直接用 Swagger /docs（零前端，最快看到效果）
1. 手机浏览器打开 `https://<你的网址>/docs`。
2. 点页面右上角 **Authorize** 🔒，在 `player_key` 框填入后端 GM 令牌后点 Authorize。
   - 没有令牌？先在 `/docs` 里调 `POST /worlds/{world_id}/players`（GM 自举）拿到 `player_key`。
3. 展开任意接口（如 `POST /relationships` 编排恋情、`POST /scandals` 引爆塌房、`POST /sim/advance` 推进时间），点 **Try it out** → **Execute**。
4. 返回 JSON 即世界演化结果；再调 `GET /characters/{id}/archive` 看人物一生档案。

> 这就是"在手机上像玩游戏一样操作它"的最小形态——后端自带，无需任何前端。

### 方式二：漂亮的中文 H5 网页（推荐长期把玩）
1. 打开 https://netlify.com ，用 **GitHub 登录**。
2. **Add new site → Import an existing project** → 选同一仓库。
3. Netlify 会**自动识别 `netlify.toml`**，配置为：
   - Build command：`npm run build`（在 `frontend/` 目录）
   - Publish：`dist/`
   - **全在云端构建**，你本地不用装 Node。
4. 点 Deploy，约 1 分钟得到 H5 网址，例如：
   ```
   https://movie-world-agent.netlify.app
   ```
5. 手机打开 → 选 **「免后端·进入演示」** 立刻看到完整 UI（内置"林星河"一生档案演示）。
6. 要连真实后端：在 Netlify 的 **Site settings → Environment variables** 里加
   `VITE_API_BASE = https://<你的Render网址>` ，然后 **Redeploy**。
   之后在 H5 里用 GM 令牌登录即可操控真实世界。

> 前端界面已包含：首页 Portal（聚合身份+世界快照+近 20 事件）、人物档案馆（商业价值断崖条 + 一生时间轴 + **岁月沉淀注脚**）、GM 工作台（编排恋情 / 引爆塌房 / 推进 Tick）。

---

## 第 ④ 步（可选）：做成真·手机 App（Capacitor）

`frontend/` 已预留 Capacitor 配置（`capacitor.config.ts`）。当 H5 跑通后，在**有 Node 的环境**
（比如 GitHub Codespaces，或你日后装了 Node）执行：
```bash
cd frontend
npm install
npx cap add android   # 生成安卓工程，可用 Android Studio 打包成 .apk
npx cap add ios       # 需 macOS + Xcode 才能出 iOS 包
```
即可把同一套 React 代码打包成安卓/iOS 原生 App。这一步**不在最简路径内**，仅作进阶说明。

---

## 常见问题

**Q：没有 GitHub 行不行？**
不行——Render / Netlify 都依赖 GitHub 拉取代码。GitHub 免费且注册极快，是这条路唯一绕不开的"工具"。

**Q：要花钱吗？**
本指南全部用**免费档**：Render free web + free Postgres、Netlify free、GitHub free。足够个人把玩。

**Q：数据库里已有数据吗？**
云端是**全新空库**，部署后需先 `POST /worlds` 开世界、造人物（见 LOCAL_GUIDE §6.14 的 e2e 脚本思路，或直接在 /docs 里手动调）。

**Q：国内手机访问慢怎么办？**
1. 把 `render.yaml` 里 `region: singapore`（已设）保留以就近。
2. 若仍慢，可在 Netlify 开启"中国加速"或后续换 Vercel 的亚太节点。

**Q：我想改界面/加页面？**
前端源码在 `frontend/src/`，页面在 `frontend/src/pages/`，组件在 `frontend/src/components/`。
改完推回 GitHub，Netlify 会自动重新构建发布。

---

## 我这边已经替你做完的事（无需你操作）
- ✅ 后端 `main.py` 默认放开 CORS（`CORS_ALLOW_ORIGINS=*`），H5 可直接跨域调用。
- ✅ `alembic/env.py` 与 `app/db/session.py` 均已读取 `DATABASE_URL`，云端迁移/运行自动连托管 PG。
- ✅ `requirements.txt` 锁定版本、`runtime.txt` 锁定 Python 3.12，保证云端可复现。
- ✅ `render.yaml`（后端+PG）、`netlify.toml`（前端云构建）已就绪。
- ✅ 前端已在此环境**编译验证通过**（`dist/` 生成，59.98 kB gzip），逻辑无错。
- ✅ 前端含「免后端演示模式」，不连后端也能看到完整 UI。

> 下一步：按第①步把仓库推上 GitHub，之后第②③步各点几次即可。需要我代推，把 GitHub Token 发我就行。
