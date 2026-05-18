"""从数据库获取攻略摘要，注入到 AI 上下文"""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.park import Strategy


def _format_snippet(title: str | None, ai_summary: str | None, structured: dict | None, content: str | None) -> str | None:
    """将攻略数据格式化为注入 System Prompt 的文本片段。优先使用结构化摘要。"""
    prefix = f"《{title}》：" if title else ""

    if structured and structured.get("is_useful"):
        parts = []
        if structured.get("summary"):
            parts.append(structured["summary"])
        if structured.get("suggested_route"):
            parts.append(f"路线：{structured['suggested_route']}")
        if structured.get("tips"):
            parts.append(f"技巧：{structured['tips']}")
        if parts:
            return prefix + " ".join(parts)

    if ai_summary:
        return prefix + ai_summary

    if content:
        return prefix + content[:200]

    return None


async def get_strategy_snippets(db: AsyncSession, park_id: str, limit: int = 5) -> list[str]:
    """
    获取点赞数最高的攻略摘要，用于注入 System Prompt。
    优先使用结构化摘要；降级到 ai_summary；再降级到原始正文截取。
    is_useful=false 的攻略跳过。
    """
    result = await db.execute(
        select(Strategy.title, Strategy.content, Strategy.ai_summary, Strategy.structured_summary)
        .where(Strategy.park_id == park_id, Strategy.is_active == True)
        .order_by(desc(Strategy.likes))
        .limit(limit * 2)  # 多取一些，过滤掉 is_useful=false 后仍能凑够 limit 条
    )
    rows = result.all()
    snippets = []
    for title, content, ai_summary, structured in rows:
        if structured and structured.get("is_useful") is False:
            continue
        snippet = _format_snippet(title, ai_summary, structured, content)
        if snippet:
            snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return snippets
