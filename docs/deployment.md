# 部署指南

## 一、本地开发环境（Windows）

### Docker Desktop 安装

1. 下载 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 安装时勾选 **Use WSL 2 instead of Hyper-V**（Windows 11 默认）
3. 安装完成后重启，验证：

```bash
docker --version        # Docker version 27.x.x
docker compose version  # Docker Compose version v2.x.x
```

4. 启动数据库：

```bash
# 项目根目录
docker compose up -d
docker compose ps   # 确认 postgres 和 redis 均为 running
```

### 前端包管理说明

当前机器 npm 与 Node 24 存在兼容性问题，**前端统一使用 yarn**：

```bash
cd frontend
yarn install   # 安装依赖
yarn dev       # 启动开发服务器
yarn build     # 构建生产包
```

---

## 二、云服务器部署（Linux）

### 服务器配置要求

| 项目 | 最低 | 推荐 |
| --- | --- | --- |
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 硬盘 | 20 GB SSD | 40 GB SSD |
| 系统 | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| 带宽 | 3 Mbps | 10 Mbps |

**参考费用**：阿里云/腾讯云轻量应用服务器 4核8G 约 ¥60-100/月。

### 服务器初始化

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 2. 安装 Docker Compose 插件
sudo apt-get install -y docker-compose-plugin

# 3. 安装 Nginx
sudo apt-get install -y nginx

# 4. 安装 Certbot（HTTPS 证书，可选）
sudo apt-get install -y certbot python3-certbot-nginx
```

### 部署步骤

```bash
# 1. 克隆代码
git clone https://github.com/your-username/youyuan-assistant.git
cd youyuan-assistant

# 2. 配置环境变量
cp backend/.env.example backend/.env
vim backend/.env   # 填入 ANTHROPIC_API_KEY 等

# 3. 构建前端
cd frontend && yarn install && yarn build
cd ..

# 4. 启动数据库
docker compose up -d postgres redis

# 5. 初始化数据库
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.init_db

# 6. 启动后端（生产模式）
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Nginx 配置

将以下内容写入 `/etc/nginx/sites-available/youyuan`：

```nginx
server {
    listen 80;
    server_name your-domain.com;   # 替换为你的域名或服务器 IP

    # 前端静态文件
    root /path/to/youyuan-assistant/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 反代
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE 流式输出必须关闭缓冲
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/youyuan /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 用 systemd 管理后端进程

创建 `/etc/systemd/system/youyuan-backend.service`：

```ini
[Unit]
Description=游园助理 FastAPI Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/youyuan-assistant/backend
Environment="PATH=/path/to/youyuan-assistant/backend/.venv/bin"
ExecStart=/path/to/youyuan-assistant/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable youyuan-backend
sudo systemctl start youyuan-backend
sudo systemctl status youyuan-backend
```

### 更新部署

```bash
git pull origin main
cd frontend && yarn build && cd ..
sudo systemctl restart youyuan-backend
```

### 开放防火墙端口

```bash
# 阿里云/腾讯云：在控制台安全组中开放 80、443 端口
# 服务器本地防火墙（如有）：
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
```

---

## 三、HTTPS 配置（有域名时）

```bash
sudo certbot --nginx -d your-domain.com
# 按提示操作，Certbot 会自动修改 Nginx 配置并续期
```

---

## 四、日常运维

| 操作 | 命令 |
| --- | --- |
| 查看后端日志 | `sudo journalctl -u youyuan-backend -f` |
| 重启后端 | `sudo systemctl restart youyuan-backend` |
| 查看数据库 | `docker compose exec postgres psql -U youyuan -d youyuan` |
| 备份数据库 | `docker compose exec postgres pg_dump -U youyuan youyuan > backup.sql` |
| 更新攻略数据 | `cd backend && python -m scripts.strategy_collector.collect --park hongkong_disney` |
