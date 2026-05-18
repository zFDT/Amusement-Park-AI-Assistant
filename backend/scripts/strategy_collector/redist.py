"""
对已入库但缺少 AI 摘要的攻略进行补充提炼

运行方式：
    cd backend
    python -m scripts.strategy_collector.redist --park hongkong_disney
    python -m scripts.strategy_collector.redist --park all
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.park import Strategy
from scripts.strategy_collector.distill import distill_batch, resolve_distill_ai_config

logger = logging.getLogger(__name__)


async def redist(park_id: str = "hongkong_disney"):
    ai_config = resolve_distill_ai_config()
    if not ai_config:
        logger.error("未配置可用的 AI 提炼配置，无法运行 AI 提炼")
        return

    async with AsyncSessionLocal() as session:
        q = select(Strategy).where(Strategy.ai_summary == None, Strategy.is_active == True)
        if park_id != "all":
            q = q.where(Strategy.park_id == park_id)
        result = await session.execute(q)
        strategies = result.scalars().all()

    if not strategies:
        logger.info("没有需要提炼的攻略")
        return

    logger.info(f"找到 {len(strategies)} 条待提炼攻略")

    items = [
        {
            "id": s.id,
            "title": s.title or "",
            "content": s.content or "",
            "images": s.image_urls or [],
        }
        for s in strategies
    ]

    summaries = await distill_batch(
        items,
        api_key=ai_config["api_key"],
        base_url=ai_config.get("base_url") or None,
        api_mode=ai_config.get("api_mode", "anthropic"),
    )

    async with AsyncSessionLocal() as session:
        for strategy_id, summary in summaries.items():
            s = await session.get(Strategy, strategy_id)
            if s:
                s.ai_summary = summary
        await session.commit()

    logger.info(f"提炼完成，成功 {len(summaries)}/{len(strategies)} 条")


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="对已入库攻略补充 AI 提炼摘要")
    parser.add_argument("--park", default="hongkong_disney", help="乐园 ID 或 'all'")
    args = parser.parse_args()

    asyncio.run(redist(park_id=args.park))
