"""
初始化数据库并导入乐园静态数据。
运行方式：python -m scripts.init_db
"""

import asyncio
import json
import hashlib
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.models.park import Base, Park, Attraction

DATA_DIR = Path(__file__).parent.parent / "app" / "data"

PARK_CONFIGS = {
    "hongkong_disney": {
        "name": "香港迪士尼乐园",
        "name_en": "Hong Kong Disneyland",
        "location": "香港大屿山",
        "timezone": "Asia/Hong_Kong",
        "queue_times_park_id": 31,
        "data_file": "hongkong_disney.json",
    },
    "shanghai_disney": {
        "name": "上海迪士尼乐园",
        "name_en": "Shanghai Disneyland",
        "location": "上海浦东新区",
        "timezone": "Asia/Shanghai",
        "queue_times_park_id": 30,
        "data_file": "shanghai_disney.json",
    },
}


async def init_db():
    engine = create_async_engine(settings.database_url, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ 数据库表创建完成")

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        for park_id, config in PARK_CONFIGS.items():
            data_file = DATA_DIR / config["data_file"]
            if not data_file.exists():
                print(f"  跳过 {park_id}（数据文件不存在）")
                continue

            # Upsert park
            existing = await session.get(Park, park_id)
            if not existing:
                park = Park(
                    id=park_id,
                    name=config["name"],
                    name_en=config["name_en"],
                    location=config["location"],
                    timezone=config["timezone"],
                    queue_times_park_id=config["queue_times_park_id"],
                )
                session.add(park)
                print(f"✓ 新增乐园: {config['name']}")
            else:
                print(f"  乐园已存在: {config['name']}")

            # Import attractions
            park_data = json.loads(data_file.read_text(encoding="utf-8"))
            count = 0
            for area in park_data.get("areas", []):
                area_name = area.get("name", "")
                for a in area.get("attractions", []):
                    existing_attr = await session.get(Attraction, a["id"])
                    coords = a.get("coordinates", {})
                    if not existing_attr:
                        attr = Attraction(
                            id=a["id"],
                            park_id=park_id,
                            name=a["name"],
                            name_en=a.get("name_en"),
                            category=a.get("category"),
                            area_name=area_name,
                            description=a.get("description"),
                            duration_minutes=a.get("duration_minutes"),
                            min_height_cm=a.get("min_height_cm"),
                            lat=coords.get("lat"),
                            lng=coords.get("lng"),
                            is_lightning_lane=a.get("is_lightning_lane", False),
                            suitable_for=a.get("suitable_for", []),
                            not_suitable_for=a.get("not_suitable_for", []),
                            tips=a.get("tips"),
                        )
                        session.add(attr)
                        count += 1

            await session.commit()
            print(f"  ✓ 导入 {count} 个项目")

    await engine.dispose()
    print("\n数据库初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_db())
