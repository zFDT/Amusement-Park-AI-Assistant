# 服务端环境变量配置与项目重启指南

> 适用服务器：`your-ssh-user@your-server-ip`（Ubuntu 22.04）
> 项目路径：`/home/<user>/amusement-park/`
> 更新日期：2026-05-24

---

## 背景

本次安全审计后，`db/upload_dump.py` 和 `backend/scripts/test_remote_db.py` 中的硬编码凭证已移除，改为从环境变量读取。服务端需要设置以下环境变量才能继续使用数据库同步功能。

---

## 一、需要新增的环境变量

### 数据库同步脚本 (`db/upload_dump.py`) 所需

在服务端的 `backend/.env` 文件中追加以下配置（**注意替换为真实值**）：

```env
# ============================================================
# 数据库同步脚本所需（db/upload_dump.py）
# ============================================================
REMOTE_HOST=your-server-ip
REMOTE_PORT=5433
SSH_USER=your-ssh-user
SSH_PASS=your-ssh-password-here
SUDO_PASS=your-sudo-password-here
PG_CONTAINER=your-postgres-container
REMOTE_DB_URL=postgresql://youyuan:youyuan@localhost:5433/youyuan
```

### 远程数据库测试脚本 (`backend/scripts/test_remote_db.py`) 所需

```env
# 测试远程数据库连接（与 DATABASE_URL 共用亦可）
REMOTE_DB_URL=postgresql://youyuan:youyuan@localhost:5433/youyuan
```

> **说明**：`REMOTE_DB_URL` 使用标准 `postgresql://` 格式（非 `+asyncpg`），与 `DATABASE_URL` 可共用。

---

## 二、配置步骤

### 步骤 1：SSH 到服务器

```bash
ssh your-ssh-user@your-server-ip
```

### 步骤 2：编辑 `.env` 文件

```bash
cd /home/<user>/amusement-park
nano backend/.env
```

在文件末尾追加上述环境变量，**填入真实的 SSH 密码和 sudo 密码**。

### 步骤 3：验证配置

```bash
cd /home/<user>/amusement-park

# 激活虚拟环境
source backend/.venv/bin/activate

# 测试远程数据库连接
REMOTE_DB_URL=postgresql://youyuan:youyuan@localhost:5433/youyuan \
  python -m scripts.test_remote_db
```

预期输出：
```
Direct connection OK - strategies: xxx
  park: 1 / Hong Kong Disneyland
Done.
```

---

## 三、重启项目

配置完成后，重启 uvicorn 使代码变更生效：

```bash
# 查看当前运行的 uvicorn 进程
ps aux | grep uvicorn

# 停止现有进程（使用 PID）
kill <pid>

# 重新启动（2 workers，监听 8001）
cd /home/<user>/amusement-park/backend
source .venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2 > /dev/null 2>&1 &

# 验证启动
sleep 2 && curl -s http://localhost:8001/health
```

> **注意**：重启会导致当前正在进行的 AI 对话会话丢失（会话存储在 Redis 中）。

---

## 四、当前服务端 `.env` 状态

服务器上的 `backend/.env` 文件**已通过 `.gitignore` 保护，不会被 git 操作覆盖**。

当前配置（部分）：
```env
DATABASE_URL=postgresql+asyncpg://youyuan:youyuan@localhost:5433/youyuan
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=["http://your-server-ip","http://localhost:5173"]
AI_DEBUG_LOGGING=true
AI_INTERNAL_PROFILES=[...]
AI_DISTILL_PROFILE_CODE=vip666
```

---

## 五、⚠️ API Key 轮换提醒

服务端 `.env` 中包含真实 API Key（Anthropic 代理 + DeepSeek），本次安全审计期间这些信息**仅在本地可见，未通过 git 泄露**。但建议尽快轮换：

1. 登录 [DeepSeek 平台](https://platform.deepseek.com) → API Keys → 吊销旧 Key，生成新 Key
2. 登录 sssaicode 代理平台 → 吊销旧 Key，生成新 Key
3. 更新 `backend/.env` 中的 `AI_INTERNAL_PROFILES`
4. 重启 uvicorn

---

## 六、常用运维命令速查

```bash
# 查看服务状态
ps aux | grep uvicorn

# 查看最新日志
tail -f /home/<user>/amusement-park/backend/logs/app.log

# 数据库同步（导出本地 → 上传远程）
cd /home/<user>/amusement-park
source backend/.venv/bin/activate
python db/upload_dump.py

# 更新代码（服务端 git 已同步到 origin/master）
cd /home/<user>/amusement-park
git fetch origin && git reset --hard origin/master
# 然后重启 uvicorn

# 检查 git 状态
cd /home/<user>/amusement-park && git status
```
