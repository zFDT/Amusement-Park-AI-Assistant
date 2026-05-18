# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 关键约束

- **前端包管理必须用 `yarn`**，不能用 `npm` 或 `npx`。当前机器 npm 11 与 Node 24 存在兼容性问题（minipass-sized 模块报错），yarn 已通过 corepack 安装。
- 后端 Python 虚拟环境在 `backend/.venv/`，Windows 激活命令为 `.venv/Scripts/activate`。
- **每完成一次完整的功能修改/优化/修复后，必须立即用中文进行 git commit 提交**，格式：`feat/fix/refactor/docs(模块): 简短描述`。例：`feat(用户): 新增登录和游园记录管理`、`fix(排队): 修复香港迪士尼 park_id 错误`。
- **每次代码修改后必须同步更新相关文档**：涉及 API/模型/脚本变更时更新 `docs/technical-design.md`；涉及用户可见功能或运行命令变更时更新 `README.md`；涉及开发约束/架构/命令变更时更新本文件（`CLAUDE.md`）。文档更新应与代码变更在同一次 commit 中提交。
- Windows 一键启动脚本已统一为根目录 `start-dev.bat`（内部调用 `start-dev.ps1`），默认后端使用 `8001`，前端使用 `5173`，并自动设置 `VITE_API_PROXY_TARGET`。
- 开发阶段如果需要查看 AI 调用的完整上下文，可在 `backend/.env` 中设置 `AI_DEBUG_LOGGING=true`；日志会输出完整请求 payload、system prompt、chunk 和最终响应，但会对密钥类 header 做脱敏。

---

## 常用命令

### 数据库（必须先启动）

```bash
docker compose up -d          # 启动 PostgreSQL(:5432) + Redis(:6379)
docker compose down           # 停止
```

### 后端

```bash
cd backend
.venv/Scripts/activate        # Windows 激活虚拟环境

# 首次或新依赖安装
pip install -r requirements.txt

# 初始化数据库并导入乐园静态数据
python -m scripts.init_db

# 启动开发服务器（热重载）
uvicorn main:app --reload --port 8001

# 采集小红书攻略（需要 Chrome + DrissionPage）
python -m scripts.strategy_collector.collect --park hongkong_disney --limit 20
python -m scripts.strategy_collector.collect --park hongkong_disney --no-distill  # 跳过 AI 提炼

# 对已入库攻略补充 AI 提炼摘要（首次迁移后执行）
python -m scripts.strategy_collector.redist --park hongkong_disney

# 强制重新提炼所有攻略（覆盖已有摘要）
python -m scripts.strategy_collector.redist --park hongkong_disney --force

# 已有数据库迁移（新增 image_urls / ai_summary / structured_summary 字段）
python -m scripts.migrate_strategy_fields
```

### 前端

```bash
cd frontend
yarn install      # 安装依赖
VITE_API_PROXY_TARGET=http://localhost:8001 yarn dev          # 开发服务器 :5173，自动代理 /api -> :8001
yarn build        # TypeScript 编译 + Vite 构建
```

---

## 架构概览

### 数据流

```
用户浏览器
  → POST /api/sessions        创建会话，生成初始路线（非流式）
  → POST /api/chat/stream     对话，SSE 流式返回 AI 回复 + 路线更新
  → GET  /api/waittimes/{id}  获取实时排队时间（Redis 缓存 5 分钟）
  → GET  /api/strategies      获取攻略列表（支持 park/platform/q/limit/offset 过滤）
```

### 后端核心逻辑（`backend/app/`）

**会话生命周期**（`api/routes/chat.py`）：
1. `POST /api/sessions`：接收 `PlanningInfo`，拉取实时排队数据 + 数据库攻略摘要，调用 `generate_initial_plan()` 生成初始路线，将 session 和消息历史存入 Redis（TTL 24h）。
2. `POST /api/chat/stream`：从 Redis 读取 session 和消息历史，重新拉取排队数据，调用 `stream_chat_response()` 以 SSE 格式流式返回。AI 回复中若包含 ` ```route ``` ` 代码块，解析后额外发送 `route_update` 事件。

**AI 客户端**（`services/ai_service.py`）：
- 支持 per-request AI 配置（`AIConfig`：`source` + `api_key` + `base_url` + `api_mode` + `model_id`，兼容旧字段 `auth_token` / `model`），并支持 `source=internal` 从 `AI_INTERNAL_PROFILES` 中按内测码读取预置配置。
- 支持的 `api_mode`：`deepseek`（推荐，OpenAI 兼容格式，默认模型 `deepseek-v4-flash`）、`openai`、`openai-responses`、`anthropic`、`gemini`、`ollama`。
- DeepSeek 特性：`reasoner` / `v4-pro` 模型自动注入 `"thinking": {"type": "enabled"}` 开启思考模式；流式响应只取 `delta.content`，跳过 `reasoning_content`（思考过程不展示给用户）。

**System Prompt 构建**（`services/prompt_builder.py`）：
- `build_system_prompt()` 将用户规划信息、实时排队 JSON、已完成项目、当前位置、攻略摘要（最多 5 条）拼装成完整 System Prompt，每次对话都重新构建。

**排队数据**（`services/waittime_service.py`）：
- 从 queue-times.com 拉取，香港迪士尼 park_id=**31**，上海迪士尼 park_id=**30**。
- 香港迪士尼返回平铺的 `rides[]`，上海迪士尼返回 `lands[].rides[]`，代码已做兼容处理。

**数据库模型**（`models/park.py`）：
- `Park` / `Attraction` / `Strategy` 三张表，用 SQLAlchemy async。
- `Attraction.queue_times_ride_id` 是与 queue-times.com 数据关联的外键。
- `Strategy` 额外字段：`image_urls`（JSON，图片 CDN URL 列表）、`ai_summary`（Text，纯文本摘要，降级显示用）、`structured_summary`（JSON，AI 结构化提炼结果，含 `is_useful`/`mentioned_attractions`/`suggested_route`/`tips`/`summary`）。
- Session 和消息历史**不入库**，只存 Redis。

**攻略采集与提炼**（`scripts/strategy_collector/`）：

- `collect.py`：DrissionPage 驱动 Chrome，从 `window.__INITIAL_STATE__` 提取搜索结果和详情（参考 xiaohongshu-mcp 方案，比 DOM 选择器更稳定）。采集完成后自动调用 AI 提炼。
- `distill.py`：调用视觉模型（支持 anthropic/openai/gemini/deepseek），分析笔记正文 + 图片（最多4张，deepseek 仅文本），输出结构化 JSON（`is_useful`、`mentioned_attractions`、`suggested_route`、`tips`、`summary`），同时写入 `ai_summary`（纯文本）和 `structured_summary`（JSON）两个字段。使用 httpx 直接调用，不依赖 anthropic SDK。
- `redist.py`：对已入库但缺少摘要的攻略批量补充提炼；`--force` 参数可强制重新提炼所有攻略。
- `strategy_service.py`：注入 System Prompt 时优先使用 `structured_summary`（跳过 `is_useful=False` 的攻略，格式化路线和技巧），降级到 `ai_summary`，再降级到原始正文截取。

**乐园静态数据**（`app/data/*.json`）：
- `hongkong_disney.json` 和 `shanghai_disney.json` 是项目数据的权威来源，`init_db.py` 读取这两个文件导入数据库。

### 前端核心逻辑（`frontend/src/`）

**状态管理**（`store/sessionStore.ts`）：
- 单一 Zustand store，通过 `persist` 中间件将 `sessionId`、`planningInfo`、`aiConfig`、`messages`、`currentRoute` 持久化到 `localStorage`（key: `youyuan-session`）。
- `aiConfig` 存储用户填写的 AI 配置，随每次 API 请求携带，后端不存储。

**对话流程**（`hooks/useChat.ts`）：
- `sendMessage()` 先向 store 追加用户消息和空的 assistant 消息占位，再调用 `streamChat()`，通过 `updateLastMessage()` 逐字更新最后一条消息内容。收到 `route_update` 事件时同步更新 `currentRoute`。

**SSE 客户端**（`services/sse.ts`）：
- 手动解析 `text/event-stream`，将 `data:` 行解析为 `SSEChunk`（`text` / `route_update` / `done` / `error`）。

**路由**：三个页面，`/`（`HomePage`：乐园选择 + 规划表单 + AI 配置面板）、`/assistant`（`AssistantPage`：对话 + 排队时间 Tab 切换）、`/strategies`（`StrategiesPage`：攻略库列表 + 详情弹窗）。

### 前后端字段命名约定

后端 Pydantic 用 `snake_case`（`session_id`、`auth_token`），前端 TypeScript 用 `camelCase`（`sessionId`、`authToken`）。`services/sse.ts` 和 `services/api.ts` 负责在发送请求时做转换，不要在其他地方做这个转换。

---

## 环境变量（`backend/.env`）

| 变量 | 说明 |
| --- | --- |
| `ANTHROPIC_API_KEY` | 服务端默认 Key，用户未配置时使用，可留空 |
| `DATABASE_URL` | 默认 `postgresql+asyncpg://youyuan:youyuan@localhost:5432/youyuan`；多机开发可改为远程地址 |
| `REDIS_URL` | 默认 `redis://localhost:6379` |
| `CORS_ORIGINS` | 默认 `["http://localhost:5173"]` |
| `CLAUDE_MODEL` | 默认 `claude-sonnet-4-6` |
| `AI_DEBUG_LOGGING` | `true` 时输出完整 AI 请求/响应到 `backend/logs/ai.log` |
| `AI_INTERNAL_PROFILES` | JSON 数组，预置 AI 配置，格式：`[{"code":"vip666","api_mode":"deepseek","base_url":"...","api_key":"...","model_id":"deepseek-v4-flash"}]`；`api_mode` 支持 `deepseek`/`anthropic`/`openai`/`gemini`/`ollama` |
| `AI_DISTILL_PROFILE_CODE` | 攻略提炼使用的内测码，对应 `AI_INTERNAL_PROFILES` 中的 `code` 字段 |

## 日志

后端启动时自动创建 `backend/logs/` 目录（已加入 `.gitignore`）：

- `backend/logs/app.log`：应用运行日志，5MB 轮转，保留 5 份
- `backend/logs/ai.log`：AI 交互完整日志（仅 `AI_DEBUG_LOGGING=true` 时写入详细内容）
- `backend/logs/access.log`：前后端 HTTP 交互请求记录（路径、状态码、耗时），5MB 轮转，保留 5 份

日志配置在 `backend/app/core/logging.py`，由 `main.py` 启动时调用 `configure_logging()` 初始化。

## 数据库同步（多机开发）

```powershell
# 导出本地 + 上传到远程服务器恢复
.\db\sync.ps1

# 仅导出到 db/dump.sql
.\db\sync.ps1 -DumpOnly
```

`db/upload_dump.py` 通过 paramiko SFTP 上传，再通过 SSH 执行 `docker cp` + `psql -f` 恢复。`dump.sql` 已加入 `.gitignore`。
