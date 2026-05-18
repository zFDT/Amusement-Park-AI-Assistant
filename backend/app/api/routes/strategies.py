"""攻略列表接口。"""

from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.park import Strategy
from app.schemas import StrategyListResponse, StrategySummary

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    park_id: str | None = None,
    platform: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """分页返回攻略列表，供前端查看采集结果。"""
    async for db in get_db():
        conditions = [Strategy.is_active == True]
        if park_id:
            conditions.append(Strategy.park_id == park_id)
        if platform:
            conditions.append(Strategy.platform == platform)
        if q:
            like = f"%{q}%"
            conditions.append(
                func.lower(func.coalesce(Strategy.title, "")).like(func.lower(like))
                | func.lower(func.coalesce(Strategy.content, "")).like(func.lower(like))
                | func.lower(func.coalesce(Strategy.ai_summary, "")).like(func.lower(like))
            )

        total_result = await db.execute(select(func.count()).select_from(Strategy).where(*conditions))
        total = int(total_result.scalar() or 0)

        result = await db.execute(
            select(Strategy)
            .where(*conditions)
            .order_by(Strategy.collected_at.desc(), Strategy.likes.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.scalars().all()

        strategies = [
            StrategySummary(
                strategy_id=item.id,
                park_id=item.park_id,
                platform=item.platform,
                source_url=item.source_url,
                title=item.title or "",
                content_excerpt=(item.content or "")[:240],
                author=item.author or "",
                likes=item.likes or 0,
                collects=item.collects or 0,
                comments=item.comments or 0,
                image_urls=item.image_urls or [],
                ai_summary=item.ai_summary,
                structured_summary=item.structured_summary,
                collected_at=item.collected_at.isoformat() if item.collected_at else "",
                mentioned_attractions=item.mentioned_attractions or [],
            )
            for item in rows
        ]

        return StrategyListResponse(total=total, strategies=strategies)
