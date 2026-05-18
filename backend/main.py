from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging
from app.core.config import settings
from app.core.redis_client import close_redis
from app.api.routes import chat, waittimes, parks, users
from app.api.routes import strategies
from app.api.routes import vision

configure_logging()

app = FastAPI(title="游园助理 API", version="0.1.0")

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


@app.on_event("shutdown")
async def shutdown():
    await close_redis()


@app.get("/health")
async def health():
    return {"status": "ok"}
