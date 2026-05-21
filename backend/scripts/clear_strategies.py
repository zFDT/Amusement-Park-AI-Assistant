"""Clear all strategies from remote DB"""
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        r = await conn.execute(text("DELETE FROM strategies"))
        print(f"Deleted {r.rowcount} strategies from remote DB")

if __name__ == "__main__":
    asyncio.run(main())
