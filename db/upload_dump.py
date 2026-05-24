"""
上传 db/dump.sql 到远程服务器并恢复到 youyuan 数据库。
由 db/sync.ps1 调用，也可单独运行：
    python db/upload_dump.py

安全说明：所有敏感信息均通过环境变量传入，不硬编码。
必需环境变量：
    REMOTE_HOST      - 远程服务器 IP/域名
    REMOTE_PORT      - 远程 PostgreSQL 端口（默认 5433）
    SSH_USER         - SSH 用户名
    SSH_PASS         - SSH 密码
    SUDO_PASS        - sudo 密码（通常与 SSH_PASS 相同）
    PG_CONTAINER     - Docker 容器名
    REMOTE_DB_URL    - 远程数据库连接串（用于 verify）
"""
import asyncpg, asyncio, paramiko, os, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DUMP_FILE = Path(__file__).parent / "dump.sql"
REMOTE_HOST = os.getenv("REMOTE_HOST", "")
REMOTE_PORT = int(os.getenv("REMOTE_PORT", "5433"))
REMOTE_DUMP = "/tmp/youyuan_dump.sql"
CONTAINER = os.getenv("PG_CONTAINER", "")
SSH_USER = os.getenv("SSH_USER", "")
SSH_PASS = os.getenv("SSH_PASS", "")
SUDO_PASS = os.getenv("SUDO_PASS", "")
REMOTE_DB_URL = os.getenv("REMOTE_DB_URL", "")


def run(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err


def main():
    if not DUMP_FILE.exists():
        print(f"ERROR: {DUMP_FILE} not found. Run sync.ps1 -DumpOnly first.")
        sys.exit(1)

    # 验证必需环境变量
    missing = []
    for var in ["REMOTE_HOST", "SSH_USER", "SSH_PASS", "SUDO_PASS", "PG_CONTAINER"]:
        if not globals()[var]:
            missing.append(var)
    if missing:
        print(f"ERROR: 缺少必需环境变量: {', '.join(missing)}")
        print("请设置以下环境变量后重试：")
        print("  REMOTE_HOST, SSH_USER, SSH_PASS, SUDO_PASS, PG_CONTAINER")
        sys.exit(1)

    size_kb = DUMP_FILE.stat().st_size / 1024
    print(f"Uploading {size_kb:.1f} KB via SFTP...")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(REMOTE_HOST, port=22, username=SSH_USER, password=SSH_PASS, timeout=30)

    sftp = client.open_sftp()
    sftp.put(str(DUMP_FILE), REMOTE_DUMP)
    sftp.close()
    print("Upload done.")

    # Copy into container
    out, err = run(client, f"echo '{SUDO_PASS}' | sudo -S docker cp {REMOTE_DUMP} {CONTAINER}:{REMOTE_DUMP}")
    print("docker cp:", out or err or "ok")

    # Drop and recreate schema to avoid conflicts, then restore
    print("Restoring (dropping existing data first)...")
    drop_sql = "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO youyuan;"
    run(client, f"echo '{SUDO_PASS}' | sudo -S docker exec {CONTAINER} psql -U youyuan -d youyuan -c \"{drop_sql}\"")

    out, err = run(client, f"echo '{SUDO_PASS}' | sudo -S docker exec {CONTAINER} psql -U youyuan -d youyuan -f {REMOTE_DUMP}")
    lines = (out + "\n" + err).strip().splitlines()
    for line in lines[-10:]:
        print(line)

    # Verify
    out, err = run(client, f"echo '{SUDO_PASS}' | sudo -S docker exec {CONTAINER} psql -U youyuan -d youyuan -c \"SELECT COUNT(*) as n FROM strategies;\"")
    print("\nVerify strategies count:", out or err)

    client.close()
    print("Remote restore complete.")


if __name__ == "__main__":
    main()
