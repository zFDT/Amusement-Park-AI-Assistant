# 游园助理 — 项目设计文档

**版本**：1.1.0  
**更新日期**：2026-05-18

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [系统架构](#3-系统架构)
4. [数据库设计](#4-数据库设计)
5. [API 接口设计](#5-api-接口设计)
6. [前端页面与组件](#6-前端页面与组件)
7. [用户操作流程](#7-用户操作流程)
8. [UML 图](#8-uml-图)
9. [状态管理设计](#9-状态管理设计)
10. [关键设计决策](#10-关键设计决策)

---

## 1. 项目概述

游园助理是一个 AI 驱动的迪士尼乐园游园路线规划 Web 应用。核心价值：

- **游前规划**：根据人员构成、偏好、体力，AI 生成个性化全日路线
- **实时排队**：每 5 分钟从 queue-times.com 拉取最新等待时间，辅助 AI 决策
- **对话调整**：游园中随时告知变化（项目关闭、已完成、当前位置），AI 实时重规划
- **用户身份**：昵称即身份，无需注册密码，支持多设备恢复会话
- **自带 Key**：用户可填入自己的 Anthropic API Key，网站无需承担 AI 费用

**当前支持乐园**：香港迪士尼乐园（上海迪士尼即将上线）

---

## 2. 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| 前端框架 | React 18 + TypeScript + Vite | SPA，无 SSR |
| 前端样式 | Tailwind CSS v4 | 原子化 CSS |
| 前端状态 | Zustand + persist | localStorage 持久化 |
| 前端路由 | React Router v7 | 客户端路由 |
| 后端框架 | FastAPI (Python 3.11+) | 异步，支持 SSE |
| ORM | SQLAlchemy 2.0 async | 异步数据库访问 |
| 数据库 | PostgreSQL 16 | 持久化存储 |
| 缓存 | Redis 7 | Session + 排队数据缓存 |
| AI | Anthropic Claude API | SSE 流式输出 |
| 排队数据 | queue-times.com API | 非官方，5 分钟缓存 |
| 容器化 | Docker Compose | 本地开发数据库 |

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                      用户浏览器                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │LoginPage │  │VisitList │  │PlanPage  │  │Assistant│ │
│  │          │  │  Page    │  │          │  │  Page   │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │              │              │              │      │
│  ┌────▼──────────────▼──────────────▼──────────────▼───┐ │
│  │              Zustand Store (localStorage)            │ │
│  │  userId / sessionId / messages / currentRoute /      │ │
│  │  completedAttractions / aiConfig / waitTimes         │ │
│  └────────────────────────┬─────────────────────────────┘ │
│                           │ fetch / SSE                    │
└───────────────────────────┼─────────────────────────────┘
                            │ HTTP / SSE  (:5173 → :8000)
┌───────────────────────────▼─────────────────────────────┐
│                    FastAPI 后端 (:8000)                   │
│                                                          │
│  /api/users/*          /api/sessions/*   /api/chat/*     │
│  /api/waittimes/*      /api/parks/*                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ ai_service   │  │waittime_svc  │  │strategy_svc   │  │
│  │ (Claude API) │  │(queue-times) │  │(DB snippets)  │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                   │          │
│  ┌──────▼─────────────────▼───────────────────▼───────┐  │
│  │              Redis (session + waittime cache)       │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              PostgreSQL (users / visits / parks)    │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │   外部服务                  │
              │  Anthropic Claude API       │
              │  queue-times.com API        │
              └────────────────────────────┘
```

### 3.2 数据流说明

| 操作 | 数据流 |
|------|--------|
| 用户登录 | 前端 → `POST /api/users/login` → PostgreSQL upsert → 返回 `is_new` |
| 查看游园列表 | 前端 → `GET /api/users/{id}/visits` → PostgreSQL → 返回 `VisitSummary[]` |
| 创建新游园 | 前端 → `POST /api/sessions` → 拉取排队+攻略 → Claude API → Redis + PostgreSQL |
| 对话调整 | 前端 → `POST /api/chat/stream` → Redis 读历史 → Claude SSE → Redis 写历史 |
| 实时排队 | 前端 → `GET /api/waittimes/{park}` → Redis 缓存（5min）→ queue-times.com |
| 归档游园 | 前端 → `PATCH /api/users/{id}/visits/{vid}/archive` → PostgreSQL status=archived |
| 换机恢复 | 前端 → `POST /api/sessions/{id}/share` → Redis 存 6 位码 → 新设备输入码恢复 |

---

## 4. 数据库设计

### 4.1 ER 图

```
┌──────────────┐       ┌─────────────────┐       ┌──────────────┐
│    users     │       │   park_visits   │       │    parks     │
├──────────────┤       ├─────────────────┤       ├──────────────┤
│ id (PK)      │──┐    │ id (PK/UUID)    │──┐    │ id (PK)      │
│ created_at   │  └───►│ user_id (FK)    │  └───►│ name         │
│ last_seen_at │       │ park_id (FK)    │       │ name_en      │
└──────────────┘       │ visit_date      │       │ timezone     │
                       │ status          │       │ queue_times_ │
                       │ planning_snap.. │       │   park_id    │
                       │ completed_attr. │       └──────┬───────┘
                       │ current_location│              │
                       │ created_at      │       ┌──────▼───────┐
                       │ updated_at      │       │ attractions  │
                       └─────────────────┘       ├──────────────┤
                                                 │ id (PK)      │
                                                 │ park_id (FK) │
                                                 │ name         │
                                                 │ category     │
                                                 │ queue_times_ │
                                                 │   ride_id    │
                                                 └──────────────┘

                                                 ┌──────────────┐
                                                 │  strategies  │
                                                 ├──────────────┤
                                                 │ id (PK)      │
                                                 │ park_id (FK) │
                                                 │ platform     │
                                                 │ title        │
                                                 │ content      │
                                                 │ likes        │
                                                 └──────────────┘
```

### 4.2 表说明

**users** — 用户表，昵称即主键，无密码

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(100) PK | 用户自填唯一标识 |
| created_at | TIMESTAMPTZ | 首次登录时间 |
| last_seen_at | TIMESTAMPTZ | 最近登录时间 |

**park_visits** — 游园记录，一次游园对应一个 AI 会话

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(50) PK | UUID，同时作为 Redis session_id |
| user_id | VARCHAR(100) FK | 关联用户 |
| park_id | VARCHAR(50) FK | 关联乐园 |
| visit_date | VARCHAR(20) | 游园日期 |
| status | VARCHAR(20) | active / archived |
| planning_snapshot | JSON | 入园前规划信息快照 |
| completed_attractions | JSON | 已完成项目 ID 列表 |
| current_location | JSON | 当前位置信息 |

**Redis 键设计**（不入库）

| 键 | TTL | 内容 |
|----|-----|------|
| `session:{uuid}` | 24h | 完整 session JSON（planning + completed + location） |
| `messages:{uuid}` | 24h | 最近 20 条对话历史 |
| `waittimes:{park_id}` | 5min | queue-times.com 响应缓存 |
| `share:{CODE}` | 7d | 6 位换机码 → session_id 映射 |

---

## 5. API 接口设计

### 5.1 用户接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/users/login` | 昵称登录/注册，返回 `is_new` |
| GET | `/api/users/{user_id}/visits` | 获取游园记录列表 |
| PATCH | `/api/users/{user_id}/visits/{visit_id}/archive` | 归档游园记录 |

### 5.2 会话接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions` | 创建新游园会话，生成初始路线 |
| PATCH | `/api/sessions/{session_id}` | 同步已完成项目和当前位置 |
| POST | `/api/sessions/{session_id}/share` | 生成 6 位换机恢复码 |
| GET | `/api/sessions/resume/{code}` | 用恢复码取回 session 状态 |

### 5.3 对话接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/stream` | SSE 流式对话，返回 text/route_update/done/error |

### 5.4 数据接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/waittimes/{park_id}` | 实时排队时间（Redis 缓存 5 分钟） |
| GET | `/api/parks` | 乐园列表 |
| GET | `/api/parks/{park_id}/attractions` | 乐园项目列表 |

### 5.5 SSE 事件格式

```
data: {"type": "text", "content": "..."}          # AI 流式文字
data: {"type": "route_update", "route": [...]}     # 路线更新
data: {"type": "done"}                             # 流结束
data: {"type": "error", "message": "..."}          # 错误
```

---

## 6. 前端页面与组件

### 6.1 页面路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | LoginPage | 昵称登录入口 |
| `/visits` | VisitListPage | 游园记录列表（需登录） |
| `/plan` | PlanPage | 选择乐园 + 填写规划表单（需登录） |
| `/assistant` | AssistantPage | AI 对话 + 排队时间（需登录 + 有 session） |

### 6.2 组件树

```
App
├── LoginPage
│   └── [昵称输入 + 登录按钮]
│
├── VisitListPage
│   ├── [用户信息头部]
│   ├── VisitCard (active) × N    → 点击进入 /assistant
│   ├── VisitCard (archived) × N  → 只读展示
│   └── [新建游园按钮]            → 跳转 /plan
│
├── PlanPage
│   ├── [乐园选择卡片]
│   ├── AIConfigPanel             → 填写 API Key / Base URL / 模型
│   └── PlanningForm              → 日期/人员/偏好/体力 → 提交创建 session
│
└── AssistantPage
    ├── [顶部导航：乐园名/日期 + 换机继续 + 重新规划]
    ├── [换机码展示条（按需显示）]
    ├── [Tab: AI助理 | 排队时间]
    ├── ChatWindow
    │   ├── MessageBubble × N     → 支持路线卡片内嵌
    │   └── ChatInput             → 快捷提问 + 文本输入 + 发送/停止
    └── WaitTimePanel
        └── [排队时间列表，按等待时间排序]
```

### 6.3 共享组件

| 组件 | 路径 | 说明 |
|------|------|------|
| Button | `ui/Button.tsx` | 通用按钮，支持 size/variant |
| Badge | `ui/Badge.tsx` | 状态标签，green/yellow/red/gray |
| AIConfigPanel | `settings/AIConfigPanel.tsx` | AI Key 配置面板，折叠式 |

---

## 7. 用户操作流程

### 7.1 首次使用流程

```
打开网站
  └─► LoginPage：输入昵称（如"小明"）
        └─► POST /api/users/login → is_new=true，写入 DB
              └─► 跳转 VisitListPage（空列表）
                    └─► 点击"新建游园"
                          └─► PlanPage：选择香港迪士尼
                                └─► 填写 AIConfigPanel（可选）
                                      └─► 填写 PlanningForm（日期/人员/偏好）
                                            └─► 提交 → POST /api/sessions
                                                  └─► AI 生成初始路线（非流式）
                                                        └─► 跳转 AssistantPage
                                                              └─► 查看路线 + 开始对话
```

### 7.2 游园中使用流程

```
AssistantPage（游园中）
  ├─► 查看"排队时间"Tab → 实时数据，每 5 分钟自动刷新
  ├─► 发送消息："我刚玩完飞越太空山，现在在幻想世界，下一个去哪？"
  │     └─► POST /api/chat/stream → SSE 流式回复 + route_update 事件
  │           └─► 路线卡片实时更新
  ├─► 发送消息："孩子累了，帮我调整成轻松路线"
  │     └─► AI 重新规划，排除刺激项目
  └─► 点击"换机继续" → 生成 6 位码（如 A3K9XZ）
        └─► 在新设备首页输入码 → 恢复完整上下文
```

### 7.3 归档游园流程

```
VisitListPage
  └─► 点击某次游园的"归档"按钮
        └─► 确认弹窗
              └─► PATCH /api/users/{id}/visits/{vid}/archive
                    └─► status = "archived"
                          └─► 游园卡片移至"历史记录"区域
                                └─► 该 session 的 /api/chat/stream 返回 403
```

### 7.4 老用户回访流程

```
打开网站
  └─► LoginPage：输入相同昵称
        └─► POST /api/users/login → is_new=false，更新 last_seen_at
              └─► 跳转 VisitListPage
                    ├─► 看到进行中的游园 → 点击继续
                    │     └─► 从 localStorage 恢复 session（如果同设备）
                    │           或从 DB 恢复 planning_snapshot（跨设备）
                    └─► 看到历史游园 → 只读查看
```

---

## 8. UML 图

### 8.1 用例图

```
                    ┌─────────────────────────────────────────┐
                    │              游园助理系统                 │
                    │                                         │
  ┌──────┐          │  ┌─────────────┐   ┌─────────────────┐ │
  │      │──登录────┼─►│  用户身份   │   │   游园规划      │ │
  │      │          │  │  管理       │   │                 │ │
  │      │──查看────┼─►│  · 昵称登录 │   │ · 选择乐园      │ │
  │      │  游园列表│  │  · 自动注册 │   │ · 填写规划信息  │ │
  │      │          │  └─────────────┘   │ · AI生成路线    │ │
  │ 游   │──创建────┼──────────────────►│ · 对话调整路线  │ │
  │ 客   │  新游园  │                    └─────────────────┘ │
  │      │          │  ┌─────────────┐   ┌─────────────────┐ │
  │      │──查看────┼─►│  实时数据   │   │   会话管理      │ │
  │      │  排队时间│  │             │   │                 │ │
  │      │          │  │ · 排队时间  │   │ · 换机恢复      │ │
  │      │──归档────┼─►│ · 5分钟刷新 │   │ · 归档游园      │ │
  │      │  游园    │  └─────────────┘   │ · 标记已完成    │ │
  └──────┘          │                    └─────────────────┘ │
                    └─────────────────────────────────────────┘
```

### 8.2 时序图 — 创建游园会话

```
前端              后端 FastAPI         Redis          PostgreSQL      Claude API
 │                     │                 │                 │               │
 │─POST /api/sessions─►│                 │                 │               │
 │                     │─fetch waittimes►│                 │               │
 │                     │◄─cache miss─────│                 │               │
 │                     │─GET queue-times.com──────────────────────────────►│(外部)
 │                     │◄─rides JSON─────────────────────────────────────── │
 │                     │─SET waittimes──►│                 │               │
 │                     │─SELECT strategies────────────────►│               │
 │                     │◄─snippets[]─────────────────────── │               │
 │                     │─messages.create────────────────────────────────── ►│
 │                     │◄─initial_plan + route──────────────────────────── ─│
 │                     │─SET session:uuid►│                 │               │
 │                     │─SET messages:uuid►│                │               │
 │                     │─INSERT park_visits────────────────►│               │
 │◄─{session_id, route}│                 │                 │               │
 │                     │                 │                 │               │
```

### 8.3 时序图 — 流式对话

```
前端              后端 FastAPI         Redis          Claude API
 │                     │                 │               │
 │─POST /api/chat/stream►│               │               │
 │                     │─GET session:uuid►│              │
 │                     │◄─session data───│               │
 │                     │─GET messages:uuid►│             │
 │                     │◄─messages[]─────│               │
 │                     │─fetch waittimes►│               │
 │                     │◄─cached data────│               │
 │                     │─messages.stream────────────────►│
 │◄─data: {text}───────│◄─text chunk─────────────────── ─│
 │◄─data: {text}───────│◄─text chunk─────────────────── ─│
 │◄─data: {route_update}│◄─(parse route block)           │
 │◄─data: {done}───────│◄─stream end─────────────────── ─│
 │                     │─SET messages:uuid►│             │
 │                     │                 │               │
```

### 8.4 状态机 — 游园记录生命周期

```
                    ┌─────────────────┐
                    │   [创建游园]     │
                    │  POST /sessions  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
              ┌────►│    active        │◄────┐
              │     │  · 可 AI 对话    │     │
              │     │  · 可更新进度    │     │
              │     └────────┬────────┘     │
              │              │ 归档          │
              │              ▼              │
              │     ┌─────────────────┐     │
              │     │   archived       │     │
              │     │  · 只读展示      │     │
              │     │  · AI 对话返回   │     │
              │     │    403 Forbidden │     │
              │     └─────────────────┘     │
              │                             │
              └─────────────────────────────┘
                    （未来：可考虑恢复归档）
```

### 8.5 类图 — 核心数据模型

```
┌─────────────────────┐
│       User          │
├─────────────────────┤
│ + id: str           │
│ + created_at: dt    │
│ + last_seen_at: dt  │
├─────────────────────┤
│ + visits: list      │
└──────────┬──────────┘
           │ 1..*
           ▼
┌─────────────────────┐         ┌─────────────────────┐
│     ParkVisit       │         │       Park           │
├─────────────────────┤         ├─────────────────────┤
│ + id: str (UUID)    │────────►│ + id: str            │
│ + user_id: str      │         │ + name: str          │
│ + park_id: str      │         │ + queue_times_id: int│
│ + visit_date: str   │         └──────────┬──────────┘
│ + status: str       │                    │ 1..*
│ + planning_snapshot │                    ▼
│ + completed_attrs   │         ┌─────────────────────┐
│ + current_location  │         │     Attraction       │
└─────────────────────┘         ├─────────────────────┤
                                │ + id: str            │
                                │ + park_id: str       │
                                │ + name: str          │
                                │ + category: str      │
                                │ + queue_times_ride_id│
                                └─────────────────────┘

┌─────────────────────┐
│     Strategy        │
├─────────────────────┤
│ + id: str           │
│ + park_id: str      │
│ + platform: str     │
│ + title: str        │
│ + content: str      │
│ + likes: int        │
└─────────────────────┘
```

---

## 9. 状态管理设计

### 9.1 Zustand Store 结构

```typescript
AppState {
  // 用户身份
  userId: string | null          // 昵称，持久化
  
  // 当前游园会话
  sessionId: string | null       // UUID，持久化
  parkId: ParkId | null          // 持久化
  planningInfo: PlanningInfo | null  // 持久化
  
  // AI 配置（用户自带 Key）
  aiConfig: AIConfig | null      // 持久化（含 authToken）
  
  // 对话状态
  messages: Message[]            // 持久化（最近 N 条）
  isStreaming: boolean           // 不持久化
  currentRoute: RouteItem[]      // 持久化
  
  // 游园进度
  completedAttractions: string[] // 持久化
  currentLocation: Location | null  // 不持久化
  
  // 排队数据
  waitTimes: Record<string, WaitTimeData>  // 不持久化
  lastWaitTimeUpdate: string | null        // 不持久化
}
```

### 9.2 持久化策略

- **持久化到 localStorage**：userId、sessionId、planningInfo、aiConfig、messages、currentRoute、completedAttractions
- **不持久化**（页面刷新后重新获取）：isStreaming、waitTimes、currentLocation
- **同步到 Redis**：completedAttractions 和 currentLocation 通过 `PATCH /api/sessions/{id}` 同步，确保跨设备一致

---

## 10. 关键设计决策

### 10.1 昵称即身份，无密码

**决策**：用户输入任意字符串作为唯一标识，相同字符串视为同一用户。

**理由**：MVP 阶段降低注册门槛，游园场景下用户不愿意注册账号。安全风险低（数据无敏感信息）。

**风险**：他人猜到昵称可查看数据。后续可加 PIN 码二次验证。

### 10.2 Session 双写（Redis + PostgreSQL）

**决策**：会话状态同时写入 Redis（快速读写）和 PostgreSQL（持久化）。

**理由**：Redis 提供低延迟的对话上下文读写；PostgreSQL 提供跨设备恢复和历史查询能力。Redis 过期（24h）后仍可从 DB 恢复 planning_snapshot。

### 10.3 消息历史只存 Redis，不入库

**决策**：对话消息历史（messages）只存 Redis，TTL 24h，不写入 PostgreSQL。

**理由**：消息量大，入库成本高；游园场景下 24h 内完成，无需长期保存；planning_snapshot 已足够恢复上下文。

### 10.4 AI Key 前端传递，后端不存储

**决策**：用户的 Anthropic API Key 存在 localStorage，每次请求携带，后端不落库。

**理由**：避免 Key 泄露风险；用户对自己的 Key 有完全控制权；符合"自带 Key"的产品定位。

### 10.5 SSE 流式输出

**决策**：AI 回复使用 Server-Sent Events 流式输出，而非等待完整响应。

**理由**：Claude 生成完整路线规划需要 10-30 秒，流式输出大幅提升感知速度；SSE 比 WebSocket 更简单，单向流足够。
