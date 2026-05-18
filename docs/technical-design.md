# 游园助理 - 技术设计文档

**版本**: v1.2  
**日期**: 2026-05-18

---

## 一、技术栈选型

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    用户浏览器                          │
│  React + TypeScript + Tailwind CSS + shadcn/ui       │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI 后端                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Chat API   │  │  WaitTime API│  │  Park API  │  │
│  │  (SSE流式)  │  │  (轮询/缓存) │  │  (静态数据)│  │
│  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  │
│         │                │                │          │
│  ┌──────▼──────┐  ┌──────▼───────┐  ┌─────▼──────┐  │
│  │ AI API      │  │queue-times   │  │ PostgreSQL  │  │
│  │(DeepSeek等) │  │    .com API  │  │  + Redis   │  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 1.2 技术选型明细

| 层次 | 技术 | 选型理由 |
|------|------|---------|
| 前端框架 | React 18 + TypeScript | 生态成熟，类型安全，组件复用性强 |
| 前端构建 | Vite | 开发体验好，HMR 快 |
| UI 组件库 | shadcn/ui + Tailwind CSS | 可定制性强，无运行时依赖 |
| 后端框架 | Python FastAPI | 原生异步，SSE 支持好，AI/数据处理生态丰富 |
| 数据库 | PostgreSQL | 结构化数据，支持 JSON 字段 |
| 缓存 | Redis | 排队时间缓存，Session 存储 |
| AI 模型 | DeepSeek / Claude / OpenAI / Gemini / Ollama | 多模型支持，默认 DeepSeek V4 Flash，兼容 OpenAI 格式 |
| 实时排队数据 | queue-times.com API | 免费，覆盖上海/香港迪士尼 |
| 流式通信 | Server-Sent Events (SSE) | 单向流式，比 WebSocket 更轻量，适合 AI 输出 |

---

## 二、项目结构

```
游园助理/
├── docs/                          # 文档
│   ├── PRD.md
│   └── technical-design.md
├── db/                            # 数据库工具
│   ├── sync.ps1                   # 本地→远程同步脚本
│   └── upload_dump.py             # SFTP 上传 + 远程恢复
├── frontend/                      # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                # shadcn/ui 基础组件
│   │   │   ├── chat/              # 对话相关组件
│   │   │   │   ├── ChatWindow.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   └── ChatInput.tsx
│   │   │   ├── planning/          # 游前规划组件
│   │   │   │   ├── PlanningForm.tsx
│   │   │   │   └── PartySelector.tsx
│   │   │   └── waittime/          # 排队时间组件
│   │   │       └── WaitTimePanel.tsx
│   │   ├── pages/
│   │   │   ├── HomePage.tsx       # 乐园选择 + 规划入口
│   │   │   ├── AssistantPage.tsx  # 主对话页面
│   │   │   └── StrategiesPage.tsx # 攻略库列表 + 详情弹窗
│   │   ├── hooks/
│   │   │   ├── useChat.ts         # 对话逻辑 hook
│   │   │   ├── useWaitTimes.ts    # 排队时间轮询 hook
│   │   │   └── useSession.ts      # Session 管理 hook
│   │   ├── services/
│   │   │   ├── api.ts             # API 请求封装（含 camelCase↔snake_case 转换）
│   │   │   └── sse.ts             # SSE 客户端封装
│   │   ├── types/
│   │   │   └── index.ts           # 全局类型定义
│   │   ├── store/
│   │   │   └── sessionStore.ts    # Zustand 状态管理
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── backend/                       # FastAPI 后端
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── chat.py        # 对话 API (SSE) + Session 管理
│   │   │       ├── parks.py       # 乐园/项目数据 API
│   │   │       ├── waittimes.py   # 排队时间 API
│   │   │       └── strategies.py  # 攻略列表 API
│   │   ├── core/
│   │   │   ├── config.py          # 配置管理
│   │   │   ├── database.py        # 数据库连接
│   │   │   ├── redis_client.py    # Redis 连接
│   │   │   └── logging.py         # 日志配置（轮转文件 handler）
│   │   ├── models/
│   │   │   └── park.py            # Park / Attraction / Strategy 模型
│   │   ├── schemas/
│   │   │   └── *.py               # Pydantic 请求/响应模型
│   │   ├── services/
│   │   │   ├── ai_service.py      # 多协议 AI 调用（DeepSeek/Anthropic/OpenAI/Gemini/Ollama）
│   │   │   ├── waittime_service.py # queue-times.com 集成
│   │   │   ├── prompt_builder.py  # System Prompt 构建
│   │   │   └── strategy_service.py # 攻略摘要注入（结构化优先）
│   │   └── data/
│   │       ├── shanghai_disney.json
│   │       └── hongkong_disney.json
│   ├── logs/                      # 运行日志（自动创建，已 gitignore）
│   │   ├── app.log
│   │   └── ai.log
│   ├── scripts/
│   │   ├── init_db.py             # 数据库初始化
│   │   ├── migrate_strategy_fields.py  # 字段迁移
│   │   └── strategy_collector/
│   │       ├── collect.py         # 采集主程序
│   │       ├── distill.py         # AI 视觉提炼（结构化 JSON 输出）
│   │       └── redist.py          # 补充提炼（支持 --force）
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
└── docker-compose.yml
```

---

## 三、API 设计

### 3.1 对话 API（核心）

**POST /api/chat/stream**

流式 SSE 接口，返回 AI 回复。

Request Body:
```json
{
  "session_id": "uuid",
  "message": "我现在在幻想世界，下一个去哪？",
  "current_location": {
    "area": "fantasyland",
    "attraction_id": null
  }
}
```

SSE Event Stream:
```
data: {"type": "text", "content": "根据当前排队情况，"}
data: {"type": "text", "content": "建议您前往..."}
data: {"type": "route_update", "route": [...]}
data: {"type": "done"}
```

---

**POST /api/sessions**

创建新会话（游前规划完成后调用）

Request Body:
```json
{
  "park_id": "shanghai_disney",
  "visit_date": "2026-06-01",
  "entry_time": "09:00",
  "exit_time": "21:00",
  "party": {
    "adults": 2,
    "children": [{"age": 6}, {"age": 8}],
    "elderly": 0,
    "special_needs": []
  },
  "preferences": ["thrill_rides", "character_meet"],
  "must_do": ["tron_lightcycle", "soaring"],
  "fitness_level": 3,
  "experience_level": "first_time",
  "special_notes": ""
}
```

Response:
```json
{
  "session_id": "uuid",
  "initial_plan": "...",  // AI 生成的初始规划文本
  "route": [...]          // 结构化路线数据
}
```

---

**GET /api/waittimes/{park_id}**

获取乐园实时排队时间

Response:
```json
{
  "park_id": "shanghai_disney",
  "last_updated": "2026-06-01T10:30:00Z",
  "attractions": [
    {
      "id": "tron_lightcycle",
      "name": "创极速光轮",
      "wait_minutes": 75,
      "status": "open",
      "is_lightning_lane": true
    }
  ]
}
```

---

**GET /api/parks/{park_id}/attractions**

获取乐园项目静态数据（含坐标、分类等）

---

**GET /api/strategies**

获取攻略列表，支持过滤和分页。

Query Params:
```
park    string   乐园 ID（如 hongkong_disney）
platform string  平台（如 xhs）
q       string   关键词搜索（标题/正文）
limit   int      每页数量（默认 20）
offset  int      偏移量（默认 0）
```

Response:
```json
{
  "total": 42,
  "items": [
    {
      "id": "abc123",
      "park_id": "hongkong_disney",
      "platform": "xhs",
      "source_url": "https://...",
      "title": "香港迪士尼攻略",
      "content": "...",
      "author": "小红书用户",
      "likes": 1200,
      "collects": 300,
      "image_urls": ["https://..."],
      "ai_summary": "...",
      "structured_summary": {
        "is_useful": true,
        "mentioned_attractions": ["飞越太空山", "迷离庄园"],
        "suggested_route": "开园先冲飞越太空山...",
        "tips": "建议购买闪电通行证...",
        "summary": "..."
      },
      "collected_at": "2026-05-18T10:00:00"
    }
  ]
}
```

---

### 3.2 AI Prompt 设计

**System Prompt 模板**：

```
你是一个专业的迪士尼乐园游园助理，帮助游客规划最优游园路线。

## 当前乐园信息
乐园：{park_name}
当前时间：{current_time}
今日开园时间：{opening_hours}

## 用户信息
人员构成：{party_description}
游园时间：{entry_time} - {exit_time}（剩余 {remaining_hours} 小时）
兴趣偏好：{preferences}
必玩项目：{must_do_attractions}
体力水平：{fitness_level}/5
游园经验：{experience_level}
特殊需求：{special_notes}

## 当前实时排队数据
{wait_times_json}

## 已完成项目
{completed_attractions}

## 当前位置
{current_location}

## 规划原则
1. 优先安排排队时间短的热门项目（开园前30分钟冲刺）
2. 按地理位置聚类，减少无效步行
3. 将高体力项目安排在上午，下午安排轻松项目
4. 为餐饮预留时间（建议避开 12:00-13:00 高峰）
5. 必玩项目必须纳入规划
6. 考虑儿童/老人的体力限制

## 输出格式
回复时，如果涉及路线规划，请在回复末尾附上结构化路线（JSON格式，用```route```代码块包裹）：
```route
[{"time": "09:00", "attraction_id": "xxx", "attraction_name": "xxx", "estimated_wait": 30, "note": "..."}]
```
```

---

## 四、数据设计

### 4.1 上海迪士尼项目数据结构

```json
{
  "park_id": "shanghai_disney",
  "park_name": "上海迪士尼乐园",
  "timezone": "Asia/Shanghai",
  "areas": [
    {
      "id": "tomorrowland",
      "name": "明日世界",
      "attractions": [
        {
          "id": "tron_lightcycle",
          "name": "创极速光轮",
          "name_en": "TRON Lightcycle / Run",
          "category": "thrill_ride",
          "duration_minutes": 3,
          "min_height_cm": 102,
          "description": "高速摩托车主题过山车，迪士尼最受欢迎项目之一",
          "coordinates": {"lat": 31.1437, "lng": 121.6680},
          "is_lightning_lane": true,
          "suitable_for": ["adults", "older_children"],
          "not_suitable_for": ["young_children", "elderly", "pregnant"],
          "tips": "开园即冲，或购买闪电通行证"
        }
      ]
    }
  ]
}
```

### 4.2 Redis 缓存策略

| Key 模式 | 内容 | TTL |
| --- | --- | --- |
| `waittimes:{park_id}` | 排队时间完整数据 | 5 分钟 |
| `session:{session_id}` | 用户会话状态 | 24 小时 |
| `messages:{session_id}` | 对话历史（最近 20 条） | 24 小时 |

### 4.3 Strategy 数据库模型

`strategies` 表存储从小红书采集的游园攻略。采集流程会先将去重后的原始攻略写入数据库，再对新入库数据执行 AI 摘要提炼；如果提炼失败，已入库攻略不会回滚，后续可通过补提炼脚本重试。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String(100) PK | source_url 的 MD5 |
| `park_id` | String(50) FK | 关联乐园 |
| `platform` | String(20) | `xhs`（小红书） |
| `source_url` | String(500) | 笔记原始链接 |
| `title` | String(500) | 笔记标题 |
| `content` | Text | 笔记正文 |
| `author` | String(200) | 作者昵称 |
| `likes` | Integer | 点赞数 |
| `collects` | Integer | 收藏数 |
| `comments` | Integer | 评论数 |
| `tags` | JSON | 关键词标签 |
| `mentioned_attractions` | JSON | 文中提及的项目名称 |
| `image_urls` | JSON | 图片 CDN URL 列表 |
| `ai_summary` | Text | 纯文本摘要（降级显示用） |
| `structured_summary` | JSON | AI 结构化提炼结果（`is_useful`/`mentioned_attractions`/`suggested_route`/`tips`/`summary`） |
| `collected_at` | DateTime | 采集时间 |
| `is_active` | Boolean | 是否启用 |

### 4.4 攻略采集与 AI 提炼流程

```text
DrissionPage (Chrome)
  → 搜索关键词（香港迪士尼攻略 等5个关键词）
  → 从 window.__INITIAL_STATE__.search.feeds 提取笔记列表（含 xsecToken）
  → 逐条导航到 /explore/{feedID}?xsec_token=...
  → 从 window.__INITIAL_STATE__.note.noteDetailMap 提取正文 + imageList
  → 入库（Strategy 表）

Claude Haiku（视觉模型）
  → 输入：笔记标题 + 正文 + 图片（最多4张，base64）
  → 输出：结构化 JSON
      {
        "is_useful": true,
        "mentioned_attractions": ["飞越太空山"],
        "suggested_route": "开园先冲飞越太空山...",
        "tips": "建议购买闪电通行证...",
        "summary": "100字以内整体摘要"
      }
  → 写入 structured_summary 字段（JSON）
  → 同时将 summary 写入 ai_summary 字段（纯文本，降级用）

System Prompt 注入
  → strategy_service.get_strategy_snippets()
  → 优先使用 structured_summary（跳过 is_useful=False，格式化路线+技巧）
  → 降级到 ai_summary，再降级到 content[:200]
  → 取点赞数最高的5条注入上下文
```

**参考**：数据提取方案参考 [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)（Go + go-rod），本项目用 Python + DrissionPage 实现相同逻辑。

---

## 五、前端状态管理

使用 Zustand 管理全局状态：

```typescript
interface AppState {
  // Session
  sessionId: string | null;
  parkId: string | null;
  
  // 用户规划信息
  planningInfo: PlanningInfo | null;
  
  // 对话
  messages: Message[];
  isStreaming: boolean;
  
  // 实时数据
  waitTimes: Record<string, WaitTimeData>;
  lastWaitTimeUpdate: Date | null;
  
  // 当前路线
  currentRoute: RouteItem[];
  completedAttractions: string[];
  
  // 地图
  currentLocation: Location | null;
}
```

---

## 六、部署方案

### 开发环境

```bash
# 前端
cd frontend && npm run dev  # :5173

# 后端
cd backend && uvicorn main:app --reload  # :8000

# 数据库（Docker）
docker-compose up postgres redis
```

### 生产环境（建议）

- 前端：Vercel / Nginx 静态托管
- 后端：Docker + 云服务器（2核4G 起步）
- 数据库：云数据库服务（RDS PostgreSQL + Redis）

---

## 七、环境变量

```env
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/youyuan
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=["http://localhost:5173"]
AI_DEBUG_LOGGING=false

# 内测码模式预置 AI 配置（JSON 数组）
AI_INTERNAL_PROFILES=[{"code":"vip666","api_mode":"anthropic","base_url":"...","api_key":"...","model_id":"claude-sonnet-4-6"}]
# 攻略提炼使用的内测码
AI_DISTILL_PROFILE_CODE=vip666
```

| 变量 | 说明 |
| --- | --- |
| `ANTHROPIC_API_KEY` | 服务端默认 Key，用户未配置时使用，可留空 |
| `DATABASE_URL` | 支持本地 Docker（`localhost:5432`）或远程服务器 |
| `REDIS_URL` | Session 和排队缓存 |
| `CORS_ORIGINS` | 允许的前端来源 |
| `AI_DEBUG_LOGGING` | `true` 时将完整 AI 上下文写入 `backend/logs/ai.log` |
| `AI_INTERNAL_PROFILES` | 预置 AI 配置数组，支持多协议（anthropic/openai/gemini/ollama） |
| `AI_DISTILL_PROFILE_CODE` | 攻略提炼脚本使用的配置 code |

---

## 八、AI 协议支持

前端统一收敛为以下配置字段：

- `source`：`custom` / `internal`
- `apiKey`
- `baseUrl`
- `apiMode`：`openai` / `openai-responses` / `ollama` / `anthropic` / `gemini`
- `modelId`
- `internalCode`

后端会根据 `apiMode` 选择对应的请求协议与流式解析方式；若 `source=internal`，则从 `AI_INTERNAL_PROFILES` 中按 `code` 匹配配置。

### 九、日志系统

后端启动时调用 `configure_logging()`（`app/core/logging.py`），注册两个轮转文件 handler：

| 文件 | Logger | 内容 | 轮转策略 |
| --- | --- | --- | --- |
| `backend/logs/app.log` | root | 应用运行日志 | 5MB，保留 5 份 |
| `backend/logs/ai.log` | `app.ai` | AI 交互完整日志 | 5MB，保留 5 份 |

当 `AI_DEBUG_LOGGING=true` 时，`app.ai` logger 会输出：

- 请求上下文（planning info、wait times、completed attractions、current location）
- 完整 `system_prompt`
- 发送给模型的请求 payload（`Authorization`/`x-api-key` header 已脱敏）
- 流式返回的每个 chunk
- 最终完整响应文本与解析出的路线 JSON

### 十、多机数据库同步

单开发者多机场景下，可通过以下方式共享数据库：

**方案 A（推荐）**：直接使用远程 PostgreSQL，将 `DATABASE_URL` 改为远程地址，无需本地 Docker PostgreSQL。

**方案 B**：本地开发，按需同步：

```powershell
# 导出本地 + 上传到远程服务器恢复
.\db\sync.ps1

# 仅导出到 db/dump.sql（不上传）
.\db\sync.ps1 -DumpOnly
```

`db/upload_dump.py` 通过 paramiko SFTP 上传 dump 文件，再通过 SSH 执行 `docker cp` + `psql -f` 恢复。`dump.sql` 已加入 `.gitignore`。
