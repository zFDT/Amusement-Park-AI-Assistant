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
