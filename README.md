# 游园助理（Amusement Park AI Assistant）

AI 驱动的主题乐园游园路线规划助理。整合实时排队数据，通过对话式 AI 为游客生成个性化游园路线，减少排队时间，提升游园体验。

**设计定位**：一个**通用主题乐园框架**，通过「乐园静态数据 + 排队数据源」可插拔的方式适配任意乐园，不局限于某一家。

**当前实现参考**：香港迪士尼乐园（数据接入 queue-times.com，`park_id` 可替换以适配其他乐园）

---

## 功能特性

- 游前规划：填写日期、人员构成、兴趣偏好，AI 生成完整路线
- 对话式调整：游园中随时告知变化，AI 实时重新规划
- 实时排队：每 5 分钟自动刷新，颜色编码直观展示
- 自定义 AI Key：支持 DeepSeek / Qwen / OpenAI / Claude / Gemini / Grok / Kimi / MiniMax 等多协议配置
- 内测码模式：可通过 `vip666` 等内测码直接启用服务端预置 AI 配置
- 开发日志：可开启 `AI_DEBUG_LOGGING=true` 输出完整 AI 请求/响应上下文

---

## 本地开发环境搭建

### 前置要求

- **Node.js** >= 18（已验证 v24）
- **Python** >= 3.11（已验证 3.13）
- **Docker Desktop for Windows**（用于 PostgreSQL + Redis）
  - 下载：[Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - 安装后确保 WSL2 已启用（Windows 11 默认已有）
  - 安装完成后 `docker --version` 和 `docker-compose --version` 均可用

> **注意**：本项目前端包管理使用 `yarn`（当前机器 npm 与 Node 24 存在兼容性问题）。

### Windows 一键启动

双击项目根目录下的 `start-dev.bat` 即可自动完成：

- 启动 Docker Compose 的 PostgreSQL + Redis
- 启动后端（默认 `8001`，自动规避被占用端口）
- 启动前端（默认 `5173`）
- 自动打开浏览器访问前端页面

### 1. 启动数据库服务

```bash
# 在项目根目录
docker-compose up -d

# 验证启动成功
docker-compose ps
```

启动后：PostgreSQL 监听 `localhost:5432`，Redis 监听 `localhost:6379`。

### 2. 配置后端

```bash
cd backend
cp .env.example .env
```

编辑 `.env`，至少填入：

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here   # 可选，用户也可在前端自行填写
DATABASE_URL=postgresql+asyncpg://youyuan:youyuan@localhost:5432/youyuan
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=["http://localhost:5173"]
AI_INTERNAL_PROFILES=[]
AI_DISTILL_PROFILE_CODE=
AI_DEBUG_LOGGING=false
```

### 3. 初始化数据库

```bash
cd backend
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS/Linux

python -m scripts.init_db
```

输出 `数据库初始化完成！` 即成功。

### 4. 启动后端

```bash
cd backend
uvicorn main:app --reload --port 8001
```

访问 [http://localhost:8001/docs](http://localhost:8001/docs) 查看 API 文档。

### 5. 启动前端

```bash
cd frontend
yarn dev
```

如果你是手动启动前端开发服务器，并希望直连本地后端，可以先设置：`VITE_API_PROXY_TARGET=http://localhost:8001`

访问 [http://localhost:5173](http://localhost:5173)

---

## 采集小红书攻略（可选）

攻略数据会注入 AI 上下文，提升推荐质量。采集器使用 DrissionPage 驱动 Chrome，通过 `window.__INITIAL_STATE__` 提取数据（比 DOM 选择器更稳定，参考 [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) 方案）。

**前置条件**：Chrome 浏览器 + DrissionPage

```bash
cd backend
pip install DrissionPage
```

**首次使用（已有数据库需先迁移）**：

```bash
# 为 strategies 表添加 image_urls / ai_summary / structured_summary 字段
python -m scripts.migrate_strategy_fields
```

**采集攻略**：

```bash
# 先单独登录小红书（推荐：登录成功后再进行采集）
python -m scripts.strategy_collector.login

# 采集香港迪士尼攻略（会弹出 Chrome 窗口，首次需手动登录小红书）
# 采集完成后自动调用 Claude Haiku 对图文内容进行 AI 提炼
python -m scripts.strategy_collector.collect --park hongkong_disney --limit 20

# 如果怀疑登录态失效，可强制重新登录后再采集
python -m scripts.strategy_collector.collect --park hongkong_disney --force-login

# 跳过 AI 提炼（节省 API 费用，适合批量采集后统一处理）
python -m scripts.strategy_collector.collect --park hongkong_disney --no-distill

# 对已入库但缺少摘要的攻略补充 AI 提炼
python -m scripts.strategy_collector.redist --park hongkong_disney

# 强制重新提炼所有攻略（覆盖已有摘要）
python -m scripts.strategy_collector.redist --park hongkong_disney --force
```

**说明**：

- 采集器会获取笔记正文 + 全部图片 URL + 点赞/收藏/评论数
- AI 提炼会输出结构化 JSON（`is_useful`、`mentioned_attractions`、`suggested_route`、`tips`、`summary`），存入 `structured_summary` 字段；同时保留纯文本摘要到 `ai_summary` 字段作为降级显示
- 采集阶段的 AI 配置在 `backend/.env` 里，建议使用 `AI_INTERNAL_PROFILES` + `AI_DISTILL_PROFILE_CODE` 来定义（例如 `api_mode="openai"` + `base_url="https://api.openai.com/v1"` + `api_key` + `model_id`）
- 如果你加了 `AI_DEBUG_LOGGING=true`，会打印完整 AI 上下文日志，便于核对
- AI 提炼支持从 `AI_INTERNAL_PROFILES` 读取多协议配置；也兼容旧版 `ANTHROPIC_API_KEY` 作为兜底
- 摘要注入 AI 上下文时比原始正文截取更精准，显著提升路线规划质量
- 建议管理员定期执行（每周一次），无需用户触发

---

## 多机开发数据库同步

如果你在多台机器上开发，可以使用共享远程 PostgreSQL 实例，或通过以下脚本手动同步：

```powershell
# 导出本地数据库 + 上传到远程服务器并恢复
.\db\sync.ps1

# 仅导出到 db/dump.sql（不上传）
.\db\sync.ps1 -DumpOnly
```

`db/sync.ps1` 会将本地 Docker 容器中的数据库导出为 `db/dump.sql`，再通过 SFTP 上传到远程服务器并恢复。`dump.sql` 已加入 `.gitignore`，不会提交到仓库。

> 如果直接使用远程数据库，只需将 `backend/.env` 中的 `DATABASE_URL` 改为远程地址即可，无需本地 Docker PostgreSQL。
>
> **注意**：`db/upload_dump.py` 的远程服务器连接信息已改为通过环境变量传入。使用前请先设置 `REMOTE_HOST`、`SSH_USER`、`SSH_PASS`、`SUDO_PASS`、`PG_CONTAINER` 等环境变量，详见脚本注释。

---

## AI 日志查阅

后端运行时会将日志写入 `backend/logs/`（自动创建，已加入 `.gitignore`）：

- `backend/logs/app.log`：应用运行日志（5MB 轮转，保留 5 份）
- `backend/logs/ai.log`：AI 交互完整日志（含 system prompt、请求 payload、流式 chunk、最终响应）

开启完整 AI 日志：在 `backend/.env` 中设置 `AI_DEBUG_LOGGING=true`，重启后端即生效。

---

## 安全说明

**本项目为开源软件，请务必注意以下安全事项：**

- **绝不提交 `.env` 文件**：该文件已加入 `.gitignore`，包含 API Key 等敏感信息。请使用 `.env.example` 作为模板
- **API Key 安全**：如果你曾在内测码配置中填写过真实 API Key，请立即前往对应平台（DeepSeek/Anthropic 等）轮换密钥
- **数据库密码**：生产环境请修改 `docker-compose.yml` 和 `.env` 中的默认密码 `youyuan`
- **脚本凭证**：`db/upload_dump.py` 等运维脚本的敏感信息已改为通过环境变量传入，详见脚本注释
- **Git 历史检查**：如果你曾将含密钥的文件提交到 Git，建议使用 `git-filter-repo` 或 `BFG Repo-Cleaner` 清理历史
- **Chrome 用户数据**： `backend/browser_data/`（小红书采集器的浏览器 Profile）包含登录态 Cookie，已在 `.gitignore` 中排除

---

## AI 配置说明

当前前端支持以下协议/模式：

- `openai`：`/chat/completions`
- `openai-responses`：`/responses`
- `ollama`：`/api/chat`
- `anthropic`：`/v1/messages`
- `gemini`：`/v1beta/models/{model}:streamGenerateContent?alt=sse`

推荐填写字段：

- `Base URL`
- `API Key`
- `API Mode`
- `Model ID`

如果选择“内测码”模式并输入 `vip666`，后端会从 `AI_INTERNAL_PROFILES` 里查找对应配置；输入错误则会返回配置错误。

开发调试时，如果你希望确认每次 AI 调用的完整上下文，可以把 `AI_DEBUG_LOGGING` 设为 `true`，后端会输出请求 payload、system prompt、消息历史、流式 chunk 和最终响应文本。

---

## 部署到云服务器（Linux）

详见 [docs/deployment.md](docs/deployment.md)。

**服务器最低配置**：2核 4GB 内存，Ubuntu 22.04，20GB SSD。  
**推荐配置**：4核 8GB，约 ¥60-100/月（阿里云/腾讯云轻量应用服务器）。

---

## 项目结构

```text
游园助理/
├── docs/                    # 文档
│   ├── PRD.md               # 产品需求文档
│   ├── technical-design.md  # 技术设计文档
│   ├── roadmap.md           # 后续规划
│   └── deployment.md        # 部署指南
├── db/                      # 数据库工具
│   ├── sync.ps1             # 本地→远程数据库同步脚本
│   └── upload_dump.py       # SFTP 上传 + 远程恢复脚本
├── frontend/                # React 18 + TypeScript 前端
├── backend/                 # Python FastAPI 后端
│   ├── app/
│   │   ├── api/routes/      # API 路由
│   │   ├── core/            # 配置、数据库、Redis、日志
│   │   ├── data/            # 乐园静态数据 JSON
│   │   ├── models/          # SQLAlchemy 数据库模型
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   └── services/        # AI、排队数据、攻略服务
│   ├── logs/                # 运行日志（自动创建，已 gitignore）
│   │   ├── app.log          # 应用日志（5MB 轮转，5份备份）
│   │   └── ai.log           # AI 交互完整日志
│   └── scripts/
│       ├── init_db.py               # 数据库初始化
│       ├── migrate_strategy_fields.py  # 字段迁移（新增 image_urls/ai_summary/structured_summary）
│       └── strategy_collector/      # 小红书攻略采集器
│           ├── collect.py           # 采集主程序（__INITIAL_STATE__ 方案）
│           ├── distill.py           # Claude Haiku 视觉提炼模块（输出结构化 JSON）
│           └── redist.py            # 已入库攻略补充提炼（支持 --force）
└── docker-compose.yml       # 本地开发数据库
```

---

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 后端 | Python FastAPI + SQLAlchemy |
| 数据库 | PostgreSQL + Redis |
| AI | Claude API（支持自定义 Key 和代理地址） |
| 排队数据 | queue-times.com API（香港迪士尼 park_id=31） |
| 流式通信 | Server-Sent Events (SSE) |
