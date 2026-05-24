from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import configure_logging, correlation_id_ctx
from app.core.config import settings
from app.core.redis_client import close_redis, get_redis
from app.core.database import engine
from app.api.routes import chat, waittimes, parks, users, strategies, vision, compare, images

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
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
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

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """请求追踪中间件：生成并注入 Correlation ID。"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = correlation_id_ctx.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        correlation_id_ctx.reset(token)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理标准的 HTTP 异常，记录路径并返回结构化 JSON。"""
    import logging
    logger = logging.getLogger("app.error")
    logger.error("HTTP Error on %s: %s - %s", request.url, exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """处理捕获所有未捕获的系统异常，防止泄露堆栈信息。"""
    import logging
    logger = logging.getLogger("app.error")
    logger.exception("Unhandled Exception on %s: %s", request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务器错误，请联系管理员或稍后重试"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数校验失败。"""
    import logging
    logger = logging.getLogger("app.error")
    logger.error("Validation Error on %s: %s", request.url, exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": "参数校验失败", "errors": exc.errors()},
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
app.include_router(images.router, prefix="/api")


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
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        status["dependencies"]["database"] = "healthy"
    except Exception:
        status["dependencies"]["database"] = "unhealthy"
        status["status"] = "degraded"

    return status
