# AGENTS.md — 游园助理 (Amusement Park AI Assistant)

AI 驱动的迪士尼乐园游园路线规划助理。前端 React 19 + TypeScript + Vite + Zustand，后端 Python + FastAPI + PostgreSQL + Redis，多模型 AI 对话（DeepSeek / OpenAI / Anthropic / Gemini）。

完整项目介绍和本地开发指南见 [README.md](./README.md)，技术架构详见 [docs/technical-design.md](./docs/technical-design.md)。

## 关键约束

- **包管理：前端必须用 `yarn`**，禁止 `npm`/`npx`（npm 11 + Node 24 兼容性问题）。
- **命名约定**：后端 Python 用 `snake_case`，前端 TypeScript 用 `camelCase`。API 层（`services/api.ts` / `services/sse.ts`）负责自动转换，不要在其他地方手动转换。
- **Commit 格式**：`feat/fix/refactor/docs(模块): 中文描述`。每次功能修改后立即提交，代码和文档变更在同一 commit 中。
- **安全红线**：禁止硬编码任何密钥/Token/密码，全部走 `.env` 环境变量。`.env` 和密钥文件（`.pem`、`.key` 等）已在 `.gitignore` 排除。
- **文档同步**：API/模型/脚本变更 → 更新 `docs/technical-design.md`；用户可见功能/命令变更 → 更新 `README.md`；开发约束/命令变更 → 更新 `CLAUDE.md`。

## 架构速览

```
frontend/src/          React 19 + TypeScript + Vite + Tailwind CSS 4
  components/          按功能模块：planning/ chat/ waittime/ settings/ ui/
  store/               Zustand 单一 store，localStorage 持久化
  services/            API 调用 + SSE 流式解析
  hooks/               useChat（对话流）、useWaitTimes（排队轮询）

backend/app/
  api/routes/          REST API：chat, waittimes, strategies, compare, parks
  services/            AI 客户端 (ai_service.py)、System Prompt 构建 (prompt_builder.py)
                      排队服务 (waittime_service.py)、攻略召回 (strategy_service.py)
  models/park.py       Park / Attraction / Strategy（SQLAlchemy async）
  data/*.json          乐园静态数据（项目白名单、园区分布）

scripts/strategy_collector/
  collect.py           小红书攻略采集（DrissionPage + Chrome）
  distill.py           AI 图文提炼（视觉模型，多协议兼容）
```

核心数据流：`POST /api/sessions` 创建会话 → `POST /api/chat/stream` SSE 流式对话 → AI 回复中的 `route` 代码块解析为路线更新。

## 常用开发命令

```bash
# 基础设施
docker compose up -d              # PostgreSQL :5432 + Redis :6379

# 后端 (cd backend && .venv/Scripts/activate)
uvicorn main:app --reload --port 8001
python -m scripts.init_db         # 初始化数据库

# 前端 (cd frontend)
yarn install
VITE_API_PROXY_TARGET=http://localhost:8001 yarn dev   # :5173

# 一键启动（Windows）
.\start-dev.bat
```

更多命令（攻略采集、数据库迁移、日志调试）见 [CLAUDE.md](./CLAUDE.md)。

## 关键约定速查

| 约定 | 说明 |
|------|------|
| 前端包管理 | `yarn` 唯一，不可用 npm |
| 字段命名 | 后端 `snake_case`，前端 `camelCase`，API 层转换 |
| Commit | `feat/fix/refactor/docs(模块): 描述` |
| 密钥管理 | 全部 `.env`，`.env.example` 仅占位符 |
| Session 存储 | 仅 Redis（TTL 24h），不入 PostgreSQL |
| 排队数据源 | queue-times.com，香港 park_id=31，上海 park_id=30 |
| 乐园数据 | `app/data/*.json` 是权威来源，init_db.py 导入 |

## 相关文档

- [README.md](./README.md) — 项目介绍、本地搭建、安全说明
- [CLAUDE.md](./CLAUDE.md) — Claude Code 专用开发指南（含完整架构详解）
- [docs/PRD.md](./docs/PRD.md) — 产品需求文档
- [docs/technical-design.md](./docs/technical-design.md) — 技术设计
- [docs/deployment.md](./docs/deployment.md) — 部署指南
- [docs/roadmap.md](./docs/roadmap.md) — 项目路线图
