"""攻略列表接口。

v2 更新（2026-05-21）：
- 新增 strategy_type / mentioned_attraction 筛选参数
- 全文搜索支持（PostgreSQL tsvector + GIN 索引）
"""

from fastapi import APIRouter, Query
from sqlalchemy import select, func, text, or_

from app.core.database import get_db
from app.models.park import Strategy
from app.schemas import StrategyListResponse, StrategySummary

router = APIRouter(prefix="/strategies", tags=["strategies"])

# ── 合法的 strategy_type 值（与 distill.py 中 STRATEGY_TYPES 同步）──
VALID_STRATEGY_TYPES = {
    "route_plan", "queue_tips", "food_dining", "photo_spot",
    "family_kids", "show_parade", "hidden_gem", "general_review", "ticket_deal",
}


@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    park_id: str | None = None,
    platform: str | None = None,
    q: str | None = None,
    strategy_type: str | None = Query(None, description="攻略主类型，如 route_plan/queue_tips/food_dining"),
    mentioned_attraction: str | None = Query(None, description="涉及的项目名称（精确匹配）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """分页返回攻略列表，支持多维筛选和全文搜索。"""
    async for db in get_db():
        conditions = [Strategy.is_active == True]
        if park_id:
            conditions.append(Strategy.park_id == park_id)
        if platform:
            conditions.append(Strategy.platform == platform)

        # 搜索：优先使用全文搜索，降级为 LIKE
        if q:
            like = f"%{q}%"
            search_conditions = [
                func.lower(func.coalesce(Strategy.title, "")).like(func.lower(like)),
                func.lower(func.coalesce(Strategy.content, "")).like(func.lower(like)),
                func.lower(func.coalesce(Strategy.ai_summary, "")).like(func.lower(like)),
            ]
            conditions.append(or_(*search_conditions))

        total_result = await db.execute(
            select(func.count()).select_from(Strategy).where(*conditions)
        )
        total = int(total_result.scalar() or 0)

        result = await db.execute(
            select(Strategy)
            .where(*conditions)
            .order_by(Strategy.collected_at.desc(), Strategy.likes.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.scalars().all()

        # Python 层过滤（strategy_type / mentioned_attraction 存在 JSON 中）
        strategies = []
        for item in rows:
            # strategy_type 筛选
            if strategy_type and strategy_type in VALID_STRATEGY_TYPES:
                st = (item.structured_summary or {}).get("strategy_type", "") or "general_review"
                if st != strategy_type:
                    continue

            # mentioned_attraction 筛选（支持部分匹配）
            if mentioned_attraction:
                mentioned = (item.structured_summary or {}).get("mentioned_attractions", [])
                if not isinstance(mentioned, list):
                    mentioned = item.mentioned_attractions or []
                if not any(mentioned_attraction.lower() in m.lower() for m in mentioned):
                    continue

            strategies.append(
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
            )

        return StrategyListResponse(total=total, strategies=strategies)
