"""
测试远程数据库连接。
用法：
    REMOTE_DB_URL=postgresql://user:pass@host:5432/dbname python -m scripts.test_remote_db

安全说明：数据库连接串通过 REMOTE_DB_URL 环境变量传入，不硬编码。
"""
import asyncio, asyncpg, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REMOTE_DB_URL = os.getenv("REMOTE_DB_URL", os.getenv("DATABASE_URL", ""))

async def test():
    if not REMOTE_DB_URL:
        print("ERROR: 请设置 REMOTE_DB_URL 或 DATABASE_URL 环境变量")
        sys.exit(1)
    # asyncpg 需要 postgresql:// 而非 postgresql+asyncpg://
    conn_url = REMOTE_DB_URL.replace("+asyncpg", "")
    conn = await asyncpg.connect(conn_url, timeout=10)
    rows = await conn.fetch('SELECT COUNT(*) as n FROM strategies')
    print('Direct connection OK - strategies:', rows[0]['n'])
    parks = await conn.fetch('SELECT id, name FROM parks ORDER BY id')
    for p in parks:
        print('  park:', p['id'], '/', p['name'])
    await conn.close()

asyncio.run(test())
print("Done.")
