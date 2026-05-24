#!/bin/bash
# ============================================================
# 游园助理服务重启脚本
# 用法：bash restart.sh
# 适用场景：代码更新后、环境变量修改后、排查问题前
# ============================================================
set -e

PROJECT_DIR="/home/zhang/amusement-park"
VENV="$PROJECT_DIR/backend/.venv/bin/activate"
LOG_DIR="$PROJECT_DIR/backend/logs"
ARCHIVE_DIR="$LOG_DIR/archive"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

echo "=== 游园助理服务重启 ==="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"

# 1. 停止现有 uvicorn 进程
echo "[1/5] 停止现有 uvicorn 进程..."
PIDS=$(ps aux | grep 'uvicorn main:app' | grep -v grep | awk '{print $2}')
if [ -n "$PIDS" ]; then
    echo "  找到进程: $PIDS"
    kill $PIDS 2>/dev/null
    sleep 2
    for pid in $PIDS; do
        if kill -0 $pid 2>/dev/null; then
            echo "  强制终止: $pid"
            kill -9 $pid 2>/dev/null
        fi
    done
    echo "  已停止"
else
    echo "  未找到运行中的 uvicorn 进程"
fi

# 2. 归档旧日志（方便每次部署后从零开始排查）
echo "[2/5] 归档旧日志..."
mkdir -p "$ARCHIVE_DIR"
for f in "$LOG_DIR"/*.log; do
    [ -f "$f" ] || continue
    basename=$(basename "$f" .log)
    archive_name="${basename}_${TIMESTAMP}.log"
    # 跳过空文件
    if [ -s "$f" ]; then
        mv "$f" "$ARCHIVE_DIR/$archive_name"
        echo "  归档: $basename.log → archive/$archive_name"
    else
        rm -f "$f"
    fi
done

# 清理旧归档（保留最近 5 次）
echo "  清理旧归档（保留最近 5 次）..."
ls -1t "$ARCHIVE_DIR"/*.log 2>/dev/null | tail -n +6 | while read old; do
    echo "  删除: $(basename "$old")"
    rm -f "$old"
done

# 3. 验证环境变量
echo "[3/5] 验证环境变量..."
cd "$PROJECT_DIR/backend"
source "$VENV"
python -c "
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
required = ['DATABASE_URL', 'REDIS_URL']
missing = [v for v in required if not os.getenv(v)]
if missing:
    print(f'  ⚠ 缺少环境变量: {missing}')
else:
    print('  ✅ 核心环境变量 OK')
" 2>&1 || echo "  ⚠ 环境变量检查跳过（python-dotenv 可能未安装）"

# 4. 重启 uvicorn
echo "[4/5] 启动 uvicorn (host=0.0.0.0, port=8001, workers=2)..."
cd "$PROJECT_DIR/backend"
nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2 > /dev/null 2>&1 &
UVICORN_PID=$!
echo "  uvicorn PID: $UVICORN_PID"

# 5. 验证启动
echo "[5/5] 验证服务..."
sleep 3
if curl -sf http://localhost:8001/docs > /dev/null 2>&1; then
    echo "  ✅ 服务启动成功！(http://localhost:8001/docs)"
else
    echo "  ⚠ 健康检查失败，请查看日志: tail -f $LOG_DIR/app.log"
fi

echo ""
echo "📁 日志位置: $LOG_DIR/"
echo "📦 历史归档: $ARCHIVE_DIR/ (保留最近 5 次)"
echo "=== 重启完成 ==="
