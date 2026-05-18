"""
数据库迁移：为 strategies 表添加字段

对已有数据库执行一次即可：
    cd backend
    python -m scripts.migrate_strategy_fields
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import AsyncSessionLocal

_MIGRATIONS = [
    ("image_urls", "ALTER TABLE strategies ADD COLUMN image_urls JSON"),
    ("ai_summary", "ALTER TABLE strategies ADD COLUMN ai_summary TEXT"),
    ("structured_summary", "ALTER TABLE strategies ADD COLUMN structured_summary JSON"),
]


async def migrate():
    async with AsyncSessionLocal() as session:
        for col, ddl in _MIGRATIONS:
            try:
                await session.execute(text(ddl))
                await session.commit()
                print(f"✓ 添加列 {col}")
            except Exception as e:
                await session.rollback()
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print(f"  列 {col} 已存在，跳过")
                else:
                    print(f"✗ 添加列 {col} 失败: {e}")

    print("迁移完成")


if __name__ == "__main__":
    asyncio.run(migrate())
