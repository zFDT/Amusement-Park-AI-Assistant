import asyncio, asyncpg, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def test():
    conn = await asyncpg.connect('postgresql://youyuan:youyuan@your-server-ip:5433/youyuan', timeout=10)
    rows = await conn.fetch('SELECT COUNT(*) as n FROM strategies')
    print('Direct connection OK - strategies:', rows[0]['n'])
    parks = await conn.fetch('SELECT id, name FROM parks ORDER BY id')
    for p in parks:
        print('  park:', p['id'], '/', p['name'])
    await conn.close()

asyncio.run(test())
print("Done.")
