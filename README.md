# 游园助理

AI 驱动的迪士尼乐园游园路线规划助理。整合实时排队数据，通过对话式 AI 为游客生成个性化游园路线，减少排队时间，提升游园体验。

**当前支持**：香港迪士尼乐园（上海迪士尼即将上线）

---

## 功能特性

- 游前规划：填写日期、人员构成、兴趣偏好，AI 生成完整路线
- 对话式调整：游园中随时告知变化，AI 实时重新规划
- 实时排队：每 5 分钟自动刷新，颜色编码直观展示
- 自定义 AI Key：支持填入自己的 Anthropic API Key 和代理地址

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
uvicorn main:app --reload --port 8000
```

访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 API 文档。

### 5. 启动前端

```bash
cd frontend
yarn dev
```

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
# 为 strategies 表添加 image_urls / ai_summary 字段
python -m scripts.migrate_strategy_fields
```

**采集攻略**：

```bash
# 采集香港迪士尼攻略（会弹出 Chrome 窗口，首次需手动登录小红书）
# 采集完成后自动调用 Claude Haiku 对图文内容进行 AI 提炼
python -m scripts.strategy_collector.collect --park hongkong_disney --limit 20

# 跳过 AI 提炼（节省 API 费用，适合批量采集后统一处理）
python -m scripts.strategy_collector.collect --park hongkong_disney --no-distill

# 对已入库但缺少摘要的攻略补充 AI 提炼
python -m scripts.strategy_collector.redist --park hongkong_disney
```

**说明**：

- 采集器会获取笔记正文 + 全部图片 URL + 点赞/收藏/评论数
- AI 提炼使用 Claude Haiku 视觉模型，分析图文内容生成100-150字实用摘要
- 摘要注入 AI 上下文时比原始正文截取更精准，显著提升路线规划质量
- 建议管理员定期执行（每周一次），无需用户触发

---

## 部署到云服务器（Linux）

详见 [docs/deployment.md](docs/deployment.md)。

**服务器最低配置**：2核 4GB 内存，Ubuntu 22.04，20GB SSD。  
**推荐配置**：4核 8GB，约 ¥60-100/月（阿里云/腾讯云轻量应用服务器）。

---

## 项目结构

```
游园助理/
├── docs/                    # 文档
│   ├── PRD.md               # 产品需求文档
│   ├── technical-design.md  # 技术设计文档
│   ├── roadmap.md           # 后续规划
│   └── deployment.md        # 部署指南
├── frontend/                # React 18 + TypeScript 前端
├── backend/                 # Python FastAPI 后端
│   ├── app/
│   │   ├── api/routes/      # API 路由
│   │   ├── core/            # 配置、数据库、Redis
│   │   ├── data/            # 乐园静态数据 JSON
│   │   ├── models/          # SQLAlchemy 数据库模型
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   └── services/        # AI、排队数据、攻略服务
│   └── scripts/
│       ├── init_db.py               # 数据库初始化
│       ├── migrate_strategy_fields.py  # 字段迁移（新增 image_urls/ai_summary）
│       └── strategy_collector/      # 小红书攻略采集器
│           ├── collect.py           # 采集主程序（__INITIAL_STATE__ 方案）
│           ├── distill.py           # Claude Haiku 视觉提炼模块
│           └── redist.py            # 已入库攻略补充提炼
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
