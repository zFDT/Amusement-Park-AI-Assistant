"""从数据库获取攻略摘要，注入到 AI 上下文"""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.park import Strategy


async def get_strategy_snippets(db: AsyncSession, park_id: str, limit: int = 5) -> list[str]:
    """
    获取点赞数最高的攻略摘要，用于注入 System Prompt。
    优先使用 AI 提炼的 ai_summary；无摘要时截取原始正文前200字。
    """
    result = await db.execute(
        select(Strategy.title, Strategy.content, Strategy.ai_summary)
        .where(Strategy.park_id == park_id, Strategy.is_active == True)
        .order_by(desc(Strategy.likes))
        .limit(limit)
    )
    rows = result.all()
    snippets = []
    for title, content, ai_summary in rows:
        if ai_summary:
            snippets.append(f"《{title}》：{ai_summary}" if title else ai_summary)
        elif content:
            snippets.append(f"《{title}》：{content[:200]}" if title else content[:200])
    return snippets
