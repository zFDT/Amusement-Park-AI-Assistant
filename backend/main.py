from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging
from app.core.config import settings
from app.core.redis_client import close_redis, get_redis
from app.core.database import engine
from app.api.routes import chat, waittimes, parks, users, strategies, vision, compare

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时检查依赖，关闭时清理资源。"""
    # Startup
    import logging
    logger = logging.getLogger("app.startup")

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("✅ Redis 连接正常: %s", settings.redis_url)
    except Exception as e:
        logger.warning("⚠️  Redis 不可用 (%s)，会话持久化将不可用", e)

    # Check Database
    try:
        async with engine.begin() as conn:
            await conn.execute(await conn.run_sync(lambda c: c.execute.__func__))
        logger.info("✅ 数据库连接正常: %s", settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url)
    except Exception as e:
        logger.warning("⚠️  数据库不可用 (%s)，攻略/排队数据将受影响", e)

    yield  # Application runs here

    # Shutdown
    await close_redis()
    await engine.dispose()
    logger.info("应用已关闭，资源已清理")


app = FastAPI(
    title="游园助理 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(waittimes.router, prefix="/api")
app.include_router(parks.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(vision.router, prefix="/api")
app.include_router(compare.router, prefix="/api")


@app.get("/api/health")
async def health():
    """健康检查端点：返回各依赖组件的状态。"""
    import logging
    logger = logging.getLogger("app.health")

    status = {
        "status": "ok",
        "version": "0.1.0",
        "dependencies": {
            "redis": "unknown",
            "database": "unknown",
        },
    }

    # Check Redis
    try:
        from app.core.redis_client import is_redis_available
        if is_redis_available():
            redis = await get_redis()
            await redis.ping()
            status["dependencies"]["redis"] = "healthy"
        else:
            status["dependencies"]["redis"] = "unavailable"
            status["status"] = "degraded"
    except Exception:
        status["dependencies"]["redis"] = "unhealthy"
        status["status"] = "degraded"

    # Check Database
    try:
        async with engine.begin() as conn:
            await conn.execute(await conn.run_sync(lambda c: c.execute.__func__))
        status["dependencies"]["database"] = "healthy"
    except Exception:
        status["dependencies"]["database"] = "unhealthy"
        status["status"] = "degraded"

    return status
