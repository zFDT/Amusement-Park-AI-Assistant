"""修复 search_vector 触发器"""
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION strategies_search_vector_update()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
                    setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'B');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        print('✓ 函数已创建')

        await conn.execute(text(
            "DROP TRIGGER IF EXISTS trg_strategies_search_vector ON strategies"
        ))
        await conn.execute(text("""
            CREATE TRIGGER trg_strategies_search_vector
            BEFORE INSERT OR UPDATE OF title, content ON strategies
            FOR EACH ROW EXECUTE FUNCTION strategies_search_vector_update()
        """))
        print('✓ 触发器已创建')

if __name__ == "__main__":
    asyncio.run(main())
