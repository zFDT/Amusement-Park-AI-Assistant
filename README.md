# 游园助理 - 启动指南

## 环境要求

- Node.js >= 18（已验证 v24）
- Python >= 3.11（已验证 3.13）
- Docker（用于 PostgreSQL + Redis）

---

## 快速启动

### 1. 启动数据库服务

```bash
docker-compose up -d
```

### 2. 配置后端环境变量

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入你的 ANTHROPIC_API_KEY
```

### 3. 启动后端

```bash
cd backend
.venv/Scripts/activate   # Windows
# 或 source .venv/bin/activate  # macOS/Linux

uvicorn main:app --reload --port 8000
```

后端启动后访问 http://localhost:8000/docs 查看 API 文档。

### 4. 启动前端

```bash
cd frontend
yarn dev
```

前端启动后访问 http://localhost:5173

---

## 项目结构

```
游园助理/
├── docs/           # PRD 和技术设计文档
├── frontend/       # React + TypeScript 前端
├── backend/        # Python + FastAPI 后端
└── docker-compose.yml
```

## 获取 Anthropic API Key

前往 https://console.anthropic.com 注册并创建 API Key，填入 `backend/.env` 的 `ANTHROPIC_API_KEY` 字段。
