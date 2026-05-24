import logging
import asyncio

import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger("app.redis")

_redis: aioredis.Redis | None = None
_redis_unavailable: bool = False


def is_redis_available() -> bool:
    """Check if Redis was successfully connected (cached result)."""
    return _redis is not None and not _redis_unavailable


async def get_redis() -> aioredis.Redis:
    global _redis, _redis_unavailable
    if _redis is not None:
        return _redis
    
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            _redis = aioredis.from_url(
                settings.redis_url, 
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )
            # Quick health check
            await _redis.ping()
            _redis_unavailable = False
            logger.info("Redis 连接成功: %s", settings.redis_url)
            return _redis
        except Exception as e:
            _redis = None
            if attempt < max_retries - 1:
                logger.warning("Redis 连接尝试 %d 失败 (%s), %d 秒后重试: %s", 
                               attempt + 1, settings.redis_url, retry_delay, e)
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                _redis_unavailable = True
                logger.error("Redis 连接最终失败 (%s)，会话功能将不可用: %s", settings.redis_url, e)
                raise ConnectionError(f"无法连接到 Redis ({settings.redis_url}): {e}") from e


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ============================================================
# 用户速率限制（per-user rate limiting）
# ============================================================

# 默认限制：每用户每分钟 5 次 AI 请求，每小时 50 次
RATE_LIMIT_MINUTE = 5       # 每分钟最大请求数
RATE_LIMIT_HOUR = 50        # 每小时最大请求数
RATE_LIMIT_WINDOW_MINUTE = 60   # 1 分钟窗口
RATE_LIMIT_WINDOW_HOUR = 3600   # 1 小时窗口


async def check_rate_limit(user_id: str, max_per_minute: int = RATE_LIMIT_MINUTE, max_per_hour: int = RATE_LIMIT_HOUR) -> tuple[bool, str]:
    """检查用户是否超出速率限制。
    
    Returns:
        (allowed, message): allowed 为 True 表示允许，False 表示被限制
    """
    if not is_redis_available():
        return True, ""  # Redis 不可用时放行

    try:
        r = await get_redis()
        key_minute = f"rate_limit:minute:{user_id}"
        key_hour = f"rate_limit:hour:{user_id}"

        # 检查每分钟限制
        count_minute = await r.get(key_minute)
        if count_minute and int(count_minute) >= max_per_minute:
            ttl = await r.ttl(key_minute)
            return False, f"请求过于频繁，请 {ttl} 秒后再试（每分钟限制 {max_per_minute} 次）"

        # 检查每小时限制
        count_hour = await r.get(key_hour)
        if count_hour and int(count_hour) >= max_per_hour:
            ttl = await r.ttl(key_hour)
            return False, f"请求次数已达上限，请 {ttl // 60} 分钟后再试（每小时限制 {max_per_hour} 次）"

        return True, ""
    except Exception:
        return True, ""  # 异常时放行，不影响正常使用


async def increment_rate_limit(user_id: str) -> None:
    """增加用户请求计数。"""
    if not is_redis_available():
        return

    try:
        r = await get_redis()
        key_minute = f"rate_limit:minute:{user_id}"
        key_hour = f"rate_limit:hour:{user_id}"

        # 使用 pipeline 保证原子性
        async with r.pipeline() as pipe:
            pipe.incr(key_minute)
            pipe.expire(key_minute, RATE_LIMIT_WINDOW_MINUTE)
            pipe.incr(key_hour)
            pipe.expire(key_hour, RATE_LIMIT_WINDOW_HOUR)
            await pipe.execute()
    except Exception:
        pass  # 计数失败不影响正常使用
