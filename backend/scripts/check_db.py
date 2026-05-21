"""Check database state"""
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT count(*) FROM strategies"))
        print(f"strategies: {r.scalar()}")

        r = await conn.execute(text("SELECT id, name FROM parks"))
        print(f"parks: {r.all()}")

        r = await conn.execute(text("SELECT count(*) FROM attractions"))
        print(f"attractions: {r.scalar()}")

        # Check search_vector column
        r = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='strategies' AND column_name='search_vector'"
        ))
        sv = r.scalar()
        print(f"search_vector column: {sv or 'NOT FOUND'}")

        # Check new indexes
        r = await conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename='strategies'"
        ))
        indexes = r.all()
        print(f"indexes: {[i[0] for i in indexes]}")

        # Sample strategies with structured_summary
        r = await conn.execute(text(
            "SELECT title, structured_summary->>'strategy_type' as stype "
            "FROM strategies WHERE is_active=true LIMIT 3"
        ))
        samples = r.all()
        print(f"sample strategies: {samples}")

if __name__ == "__main__":
    asyncio.run(main())
