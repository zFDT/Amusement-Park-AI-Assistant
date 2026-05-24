"""从数据库获取攻略摘要，注入到 AI 上下文。

v2 更新（2026-05-21）：
- 多路召回 + 重排序（热门 / 类型多样 / 偏好匹配 / 时效性）
- 格式化增强：类型标签前置 + 结构化 Markdown
- 向后兼容旧版 structured_summary（无 strategy_type 字段时默认 general_review）
"""

import logging
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, desc, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.park import Strategy
from app.core.redis_client import get_redis, is_redis_available

logger = logging.getLogger("app.strategy")

# ── 攻略类型中文标签 ──────────────────────────────────────────────────────

_STRATEGY_TYPE_LABELS: dict[str, str] = {
    "route_plan": "路线规划",
    "queue_tips": "排队技巧",
    "food_dining": "餐饮推荐",
    "photo_spot": "拍照打卡",
    "family_kids": "亲子攻略",
    "show_parade": "表演巡游",
    "hidden_gem": "隐藏玩法",
    "general_review": "游园分享",
    "ticket_deal": "票务优惠",
}

# ── 用户偏好 → 攻略类型映射 ─────────────────────────────────────────────────

_PREFERENCE_TO_STRATEGY_TYPES: dict[str, list[str]] = {
    "thrill_rides": ["queue_tips", "route_plan"],
    "family_rides": ["family_kids", "route_plan"],
    "shows": ["show_parade"],
    "character_meet": ["photo_spot", "hidden_gem"],
    "photography": ["photo_spot"],
    "dining": ["food_dining"],
    "parades": ["show_parade"],
}

# ── 格式化 ──────────────────────────────────────────────────────────────────


def _format_snippet(
    title: str | None,
    ai_summary: str | None,
    structured: dict | None,
    content: str | None,
) -> str | None:
    """将攻略数据格式化为注入 System Prompt 的文本片段。优先使用结构化摘要。

    v2 新增：类型标签前置、涉及项目标注。
    """
    if not title and not structured and not ai_summary and not content:
        return None

    is_useful = structured.get("is_useful") if structured else None
    if is_useful is False:
        return None

    type_label = ""
    if structured:
        stype = structured.get("strategy_type", "") or "general_review"
        if stype in _STRATEGY_TYPE_LABELS:
            type_label = f"[{_STRATEGY_TYPE_LABELS[stype]}] "

    title_part = f"《{title}》" if title else ""

    if structured and structured.get("is_useful"):
        parts = []
        if structured.get("summary"):
            parts.append(structured["summary"])

        # 涉及项目
        mentioned = structured.get("mentioned_attractions")
        if isinstance(mentioned, list) and mentioned:
            parts.append(f"涉及项目：{'、'.join(mentioned[:5])}")

        if structured.get("suggested_route"):
            parts.append(f"路线：{structured['suggested_route']}")
        if structured.get("tips"):
            parts.append(f"技巧：{structured['tips']}")

        if parts:
            return type_label + title_part + " " + " | ".join(parts)

    if ai_summary:
        return type_label + title_part + " " + ai_summary

    if content:
        return type_label + title_part + " " + content[:200]

    return None


# ── 多路召回查询 ───────────────────────────────────────────────────────────


async def _fetch_hot_strategies(
    db: AsyncSession, park_id: str, limit: int = 10
) -> list[tuple]:
    """路 1：热门攻略（按点赞排序）"""
    result = await db.execute(
        select(
            Strategy.id, Strategy.title, Strategy.content,
            Strategy.ai_summary, Strategy.structured_summary,
            Strategy.likes, Strategy.collected_at,
        )
        .where(Strategy.park_id == park_id, Strategy.is_active == True)
        .order_by(desc(Strategy.likes))
        .limit(limit)
    )
    return list(result.all())


async def _fetch_diverse_strategies(
    db: AsyncSession, park_id: str, limit_per_type: int = 2
) -> list[tuple]:
    """路 2：类型多样性——每种 strategy_type 各取 top N 条。

    由于 strategy_type 存在 JSON 字段内无法直接 SQL 过滤，
    先取足够多热门攻略，在 Python 层按类型分组。
    """
    result = await db.execute(
        select(
            Strategy.id, Strategy.title, Strategy.content,
            Strategy.ai_summary, Strategy.structured_summary,
            Strategy.likes, Strategy.collected_at,
        )
        .where(Strategy.park_id == park_id, Strategy.is_active == True)
        .order_by(desc(Strategy.likes))
        .limit(50)
    )
    all_rows = list(result.all())

    # 按 strategy_type 分组，每组取 top N
    by_type: dict[str, list[tuple]] = {}
    for row in all_rows:
        structured = row[4]  # Strategy.structured_summary
        stype = (structured or {}).get("strategy_type", "") or "general_review"
        if structured and structured.get("is_useful") is False:
            continue
        by_type.setdefault(stype, []).append(row)

    diverse: list[tuple] = []
    for stype in [
        "route_plan", "queue_tips", "food_dining", "photo_spot",
        "family_kids", "show_parade", "hidden_gem", "general_review", "ticket_deal",
    ]:
        rows = by_type.get(stype, [])
        diverse.extend(rows[:limit_per_type])

    return diverse


async def _fetch_preference_matched_strategies(
    db: AsyncSession, park_id: str, preferences: list[str], limit: int = 10
) -> list[tuple]:
    """路 3：偏好匹配——根据用户偏好标签筛选相关类型的攻略"""
    if not preferences:
        return []

    target_types: set[str] = set()
    for pref in preferences:
        types_for_pref = _PREFERENCE_TO_STRATEGY_TYPES.get(pref, [])
        target_types.update(types_for_pref)

    if not target_types:
        return []

    result = await db.execute(
        select(
            Strategy.id, Strategy.title, Strategy.content,
            Strategy.ai_summary, Strategy.structured_summary,
            Strategy.likes, Strategy.collected_at,
        )
        .where(Strategy.park_id == park_id, Strategy.is_active == True)
        .order_by(desc(Strategy.likes))
        .limit(50)
    )
    all_rows = list(result.all())

    matched: list[tuple] = []
    for row in all_rows:
        structured = row[4]
        if structured and structured.get("is_useful") is False:
            continue
        stype = (structured or {}).get("strategy_type", "") or ""
        if stype in target_types:
            matched.append(row)
        if len(matched) >= limit:
            break

    return matched


async def _fetch_recent_strategies(
    db: AsyncSession, park_id: str, days: int = 30, limit: int = 10
) -> list[tuple]:
    """路 4：时效性——最近 N 天采集的攻略"""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            Strategy.id, Strategy.title, Strategy.content,
            Strategy.ai_summary, Strategy.structured_summary,
            Strategy.likes, Strategy.collected_at,
        )
        .where(
            Strategy.park_id == park_id,
            Strategy.is_active == True,
            Strategy.collected_at >= since,
        )
        .order_by(desc(Strategy.likes))
        .limit(limit)
    )
    return list(result.all())


# ── 去重与多样性保障 ───────────────────────────────────────────────────────


def _deduplicate_and_rerank(
    hot: list[tuple],
    diverse: list[tuple],
    preference: list[tuple],
    recent: list[tuple],
    target_count: int = 5,
) -> list[tuple]:
    """多路召回结果去重并重排序，确保多样性。

    策略：
    1. 按权重交错排列（热门优先，再穿插多样化/偏好/时效）
    2. 去重（以 strategy.id 为 key）
    3. 确保至少 3 种不同 strategy_type（如可能）
    4. 返回 target_count 条
    """
    seen_ids: set[str] = set()
    ranked: list[tuple] = []
    type_counts: dict[str, int] = {}

    # 交错排列：热门 → 多样 → 偏好 → 时效 → 热门 → ...
    all_sources = [
        (hot, "hot"),
        (diverse, "diverse"),
        (preference, "preference"),
        (recent, "recent"),
    ]

    max_len = max(len(src) for src, _ in all_sources) if all_sources else 0

    for i in range(max_len):
        for source_list, src_label in all_sources:
            if i < len(source_list):
                row = source_list[i]
                sid = row[0]  # Strategy.id
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    structured = row[4] or {}
                    stype = structured.get("strategy_type", "") or "general_review"
                    ranked.append(row)
                    type_counts[stype] = type_counts.get(stype, 0) + 1

    # 多样性调整：如果结果中类型数 < 3，从多样化池中补充
    if len(set(type_counts.keys())) < 3:
        for row in diverse:
            if len(ranked) >= target_count * 2:
                break
            sid = row[0]
            structured = row[4] or {}
            stype = structured.get("strategy_type", "") or "general_review"
            if sid not in seen_ids and stype not in type_counts:
                seen_ids.add(sid)
                ranked.append(row)
                type_counts[stype] = 1

    return ranked[:target_count]


# ── 公共接口 ────────────────────────────────────────────────────────────────


async def get_strategy_snippets(
    db: AsyncSession,
    park_id: str,
    limit: int = 5,
    preferences: list[str] | None = None,
) -> list[str]:
    """
    多路召回攻略摘要，用于注入 System Prompt。

    v2 新增参数/特性：
    - preferences: 用户偏好标签列表，用于偏好匹配召回
    - Redis 缓存：针对相同 park_id/limit/pref 缓存 1 小时，减少高并发下的数据库压力
    """
    # ── 缓存读取 ────────────────────────────────────────────────────────
    # 构造唯一缓存键：含版本号 v2、乐园ID、数量限制、排序后的偏好列表
    pref_str = ",".join(sorted(preferences or []))
    cache_key = f"strategy_snippets:v2:{park_id}:{limit}:{pref_str}"
    
    if is_redis_available():
        try:
            redis = await get_redis()
            cached_data = await redis.get(cache_key)
            if cached_data:
                logger.debug("Strategy snippets cache hit: %s", cache_key)
                return json.loads(cached_data)
        except Exception as e:
            logger.warning("Strategy snippets cache read failed: %s", e)

    # ── 并行召回 (SQLAlchemy 不真正支持 await 两个 execute, 这里是顺序执行但逻辑独立) ──
    hot = await _fetch_hot_strategies(db, park_id, limit=15)
    diverse = await _fetch_diverse_strategies(db, park_id, limit_per_type=2)
    preference = await _fetch_preference_matched_strategies(
        db, park_id, preferences or [], limit=10,
    )
    recent = await _fetch_recent_strategies(db, park_id, days=60, limit=5)

    # 去重 + 重排序 + 多样性保障
    ranked = _deduplicate_and_rerank(hot, diverse, preference, recent, target_count=limit)

    # 格式化输出
    snippets: list[str] = []
    for row in ranked:
        _, title, content, ai_summary, structured, *_ = row
        snippet = _format_snippet(title, ai_summary, structured, content)
        if snippet:
            snippets.append(snippet)

    # ── 缓存存储 ────────────────────────────────────────────────────────
    if is_redis_available() and snippets:
        try:
            redis = await get_redis()
            # 缓存 1 小时，过期时间随机浮动避免缓存雪崩
            ttl = 3600 + (300 if hash(cache_key) % 2 == 0 else -300)
            await redis.setex(cache_key, ttl, json.dumps(snippets))
        except Exception as e:
            logger.warning("Strategy snippets cache write failed: %s", e)

    logger.info(
        "攻略召回: park=%s limit=%d pref=%s → hot=%d diverse=%d pref_match=%d recent=%d → final=%d types=%s (Cache Miss)",
        park_id, limit, preferences,
        len(hot), len(diverse), len(preference), len(recent),
        len(snippets),
        [(((row[4] or {}).get("strategy_type") or "?")) for row in ranked],
    )

    return snippets


async def get_strategy_snippets_simple(
    db: AsyncSession, park_id: str, limit: int = 5
) -> list[str]:
    """
    简化版（兼容旧调用）：仅按点赞排序，不涉及偏好匹配。
    用于不需要用户上下文的场景（如前端攻略列表预览）。
    """
    result = await db.execute(
        select(Strategy.title, Strategy.content, Strategy.ai_summary, Strategy.structured_summary)
        .where(Strategy.park_id == park_id, Strategy.is_active == True)
        .order_by(desc(Strategy.likes))
        .limit(limit * 2)
    )
    rows = result.all()
    snippets = []
    for title, content, ai_summary, structured in rows:
        snippet = _format_snippet(title, ai_summary, structured, content)
        if snippet:
            snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return snippets
