"""
迁移脚本：Phase 1 数据库优化 (2026-05-21)

变更内容：
1. strategies 表新增 search_vector 列（TSVECTOR 全文搜索）
2. 创建 GIN 索引加速全文搜索
3. 新增复合索引：ix_strategies_park_active_likes、ix_strategies_park_active_date
4. 更新 PostgreSQL 连接池配置（app/core/database.py）
5. 填充已有数据的 search_vector

运行方式：
    cd backend
    python -m scripts.migrate_phase1
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine, AsyncSessionLocal
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


async def add_search_vector_column():
    """为 strategies 表添加 search_vector TSVECTOR 列和 GIN 索引"""
    async with engine.begin() as conn:
        # 添加列（如已存在则跳过）
        try:
            await conn.execute(text(
                "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS search_vector tsvector"
            ))
            logger.info("✓ 已添加 search_vector 列")
        except Exception as e:
            logger.warning("添加 search_vector 列失败（可能已存在）: %s", e)

        # 创建 GIN 索引
        try:
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_strategies_search_vector "
                "ON strategies USING GIN (search_vector)"
            ))
            logger.info("✓ 已创建 search_vector GIN 索引")
        except Exception as e:
            logger.warning("创建 GIN 索引失败: %s", e)

        # 填充已有数据的 search_vector（title 权重 A，content 权重 B）
        try:
            result = await conn.execute(text(
                "UPDATE strategies SET search_vector = "
                "setweight(to_tsvector('simple', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('simple', coalesce(content, '')), 'B') "
                "WHERE search_vector IS NULL"
            ))
            logger.info("✓ 已填充 %s 条记录的 search_vector", result.rowcount)
        except Exception as e:
            logger.warning("填充 search_vector 失败: %s", e)


async def add_composite_indexes():
    """添加复合索引以优化多路召回查询"""
    async with engine.begin() as conn:
        indexes = [
            ("ix_strategies_park_active_likes",
             "CREATE INDEX IF NOT EXISTS ix_strategies_park_active_likes ON strategies (park_id, is_active, likes DESC)"),
            ("ix_strategies_park_active_date",
             "CREATE INDEX IF NOT EXISTS ix_strategies_park_active_date ON strategies (park_id, is_active, collected_at DESC)"),
        ]
        for idx_name, sql in indexes:
            try:
                await conn.execute(text(sql))
                logger.info("✓ 已创建索引 %s", idx_name)
            except Exception as e:
                logger.warning("创建索引 %s 失败: %s", idx_name, e)


async def create_tsvector_trigger():
    """创建触发器：insert/update 时自动更新 search_vector"""
    async with engine.begin() as conn:
        # 创建函数
        try:
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION strategies_search_vector_update() RETURNS trigger AS $$
                BEGIN
                    NEW.search_vector :=
                        setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
                        setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'B');
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """))
            logger.info("✓ 已创建 search_vector 自动更新函数")
        except Exception as e:
            logger.warning("创建触发器函数失败: %s", e)

        # 创建触发器
        try:
            await conn.execute(text("""
                DROP TRIGGER IF EXISTS trg_strategies_search_vector ON strategies;
                CREATE TRIGGER trg_strategies_search_vector
                BEFORE INSERT OR UPDATE OF title, content ON strategies
                FOR EACH ROW EXECUTE FUNCTION strategies_search_vector_update();
            """))
            logger.info("✓ 已创建 search_vector 自动更新触发器")
        except Exception as e:
            logger.warning("创建触发器失败: %s", e)


async def main():
    logger.info("=" * 60)
    logger.info("Phase 1 数据库迁移开始")
    logger.info("=" * 60)

    await add_search_vector_column()
    await add_composite_indexes()
    await create_tsvector_trigger()

    logger.info("=" * 60)
    logger.info("Phase 1 数据库迁移完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
