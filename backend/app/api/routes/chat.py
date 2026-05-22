import json
import logging
import random
import string
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.redis_client import get_redis, is_redis_available
from app.core.database import get_db
from app.schemas import (
    ChatRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    UpdateSessionRequest,
    UpdateSessionResponse,
    ShareSessionResponse,
    ResumeSessionResponse,
    PlanningInfo,
)
from app.services.ai_service import generate_initial_plan, generate_initial_plan_stream, stream_chat_response
from app.services.waittime_service import fetch_wait_times, wait_times_to_json
from app.services.strategy_service import get_strategy_snippets

router = APIRouter()
logger = logging.getLogger("app.chat")

_SHARE_CODE_TTL = 7 * 24 * 3600  # 7 days


def _generate_share_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


async def _check_redis_available() -> None:
    """Raise 503 if Redis is not available (critical dependency for sessions)."""
    if not is_redis_available():
        raise HTTPException(
            status_code=503,
            detail="服务暂不可用：会话存储(Redis)未连接，请稍后重试或联系管理员",
        )


async def _get_session(session_id: str) -> dict:
    await _check_redis_available()
    redis = await get_redis()
    raw = await redis.get(f"session:{session_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="会话未找到或已过期")
    return json.loads(raw)


async def _save_session(session_id: str, data: dict) -> None:
    await _check_redis_available()
    redis = await get_redis()
    await redis.setex(
        f"session:{session_id}",
        settings.session_ttl_seconds,
        json.dumps(data, ensure_ascii=False),
    )


async def _get_messages(session_id: str) -> list[dict]:
    await _check_redis_available()
    redis = await get_redis()
    raw = await redis.get(f"messages:{session_id}")
    return json.loads(raw) if raw else []


async def _save_messages(session_id: str, messages: list[dict]) -> None:
    await _check_redis_available()
    redis = await get_redis()
    trimmed = messages[-20:]
    await redis.setex(
        f"messages:{session_id}",
        settings.session_ttl_seconds,
        json.dumps(trimmed, ensure_ascii=False),
    )


from app.models.park import ParkVisit


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    redis_ok = is_redis_available()

    try:
        wait_times = await fetch_wait_times(request.park_id)
        wt_json = wait_times_to_json(wait_times)
    except Exception as e:
        logger.warning("排队数据获取失败: %s", e)
        wt_json = "{}"

    strategy_snippets: list[str] = []
    try:
        async for db in get_db():
            strategy_snippets = await get_strategy_snippets(
                db, request.park_id,
                preferences=request.preferences if hasattr(request, 'preferences') else None,
            )
    except Exception as e:
        logger.warning("攻略摘要获取失败: %s", e)

    # Generate plan first — this is the expensive/critical part
    initial_plan, route = await generate_initial_plan(
        request, wt_json, strategy_snippets, ai_config=request.ai_config
    )

    # Try to persist session to Redis (non-blocking — don't fail the response)
    session_persisted = False
    if redis_ok:
        try:
            session_data = {
                "session_id": session_id,
                "planning": request.model_dump(),
                "completed_attractions": [],
                "current_location": None,
                "user_id": request.user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await _save_session(session_id, session_data)

            initial_message = {"role": "assistant", "content": initial_plan}
            await _save_messages(session_id, [initial_message])
            session_persisted = True
        except Exception:
            logger.warning("会话 %s 持久化失败（Redis 异常），AI 规划结果仍返回给用户", session_id)
    else:
        logger.warning("Redis 不可用，会话 %s 不会持久化（AI 规划结果仍返回）", session_id)

    # Persist visit record to DB if user_id provided
    if request.user_id:
        try:
            async for db in get_db():
                visit = ParkVisit(
                    id=session_id,
                    user_id=request.user_id,
                    park_id=request.park_id,
                    visit_date=request.visit_date,
                    planning_snapshot=request.model_dump(),
                    completed_attractions=[],
                )
                db.add(visit)
                await db.commit()
        except Exception:
            logger.warning("游园记录入库失败（DB 异常），不影响会话结果")

    return CreateSessionResponse(
        session_id=session_id,
        initial_plan=initial_plan,
        route=route,
    )


@router.post("/sessions/stream")
async def create_session_stream(request: CreateSessionRequest):
    """流式版本：逐字返回 AI 路线规划，前端可实时展示生成进度。"""
    session_id = str(uuid.uuid4())

    try:
        wait_times = await fetch_wait_times(request.park_id)
        wt_json = wait_times_to_json(wait_times)
    except Exception as e:
        logger.warning("排队数据获取失败: %s", e)
        wt_json = "{}"

    strategy_snippets: list[str] = []
    try:
        async for db in get_db():
            strategy_snippets = await get_strategy_snippets(
                db, request.park_id,
                preferences=request.preferences if hasattr(request, 'preferences') else None,
            )
    except Exception as e:
        logger.warning("攻略摘要获取失败: %s", e)

    async def event_stream():
        accumulated = ""
        try:
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        except Exception:
            pass

        try:
            async for chunk in generate_initial_plan_stream(
                request, wt_json, strategy_snippets, ai_config=request.ai_config
            ):
                if chunk["type"] == "text":
                    accumulated += chunk["content"]
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "route":
                    yield f"data: {json.dumps({'type': 'route', 'route': chunk['route']})}\n\n"
                elif chunk["type"] == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': chunk['message']})}\n\n"
                    return
                elif chunk["type"] == "done":
                    break
        except Exception as e:
            logger.error("流式规划生成失败: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # Persist session
        redis_ok = is_redis_available()
        if redis_ok:
            try:
                session_data = {
                    "session_id": session_id,
                    "planning": request.model_dump(),
                    "completed_attractions": [],
                    "current_location": None,
                    "user_id": request.user_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                await _save_session(session_id, session_data)
                await _save_messages(session_id, [{"role": "assistant", "content": accumulated}])
            except Exception:
                logger.warning("会话持久化失败")

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.patch("/sessions/{session_id}", response_model=UpdateSessionResponse)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Sync completed attractions and current location from client to Redis and DB."""
    session = await _get_session(session_id)

    if request.completed_attractions is not None:
        session["completed_attractions"] = request.completed_attractions
    if request.current_location is not None:
        session["current_location"] = request.current_location

    await _save_session(session_id, session)

    # Mirror to DB if visit record exists
    try:
        async for db in get_db():
            visit = await db.get(ParkVisit, session_id)
            if visit:
                if request.completed_attractions is not None:
                    visit.completed_attractions = request.completed_attractions
                if request.current_location is not None:
                    visit.current_location = request.current_location
                await db.commit()
    except Exception:
        pass

    return UpdateSessionResponse(
        session_id=session_id,
        completed_attractions=session["completed_attractions"],
    )


@router.post("/sessions/{session_id}/share", response_model=ShareSessionResponse)
async def share_session(session_id: str):
    """Generate a short 6-char code that maps to this session_id for cross-device resume."""
    await _get_session(session_id)  # verify session exists

    code = _generate_share_code()
    redis = await get_redis()
    # Ensure uniqueness — retry up to 5 times
    for _ in range(5):
        existing = await redis.get(f"share:{code}")
        if not existing:
            break
        code = _generate_share_code()

    await redis.setex(f"share:{code}", _SHARE_CODE_TTL, session_id)

    return ShareSessionResponse(code=code, expires_in_seconds=_SHARE_CODE_TTL)


@router.get("/sessions/resume/{code}", response_model=ResumeSessionResponse)
async def resume_session(code: str):
    """Look up a session by share code and return its state for cross-device resume."""
    redis = await get_redis()
    session_id_bytes = await redis.get(f"share:{code.upper()}")
    if not session_id_bytes:
        raise HTTPException(status_code=404, detail="Invalid or expired share code")

    session_id = session_id_bytes if isinstance(session_id_bytes, str) else session_id_bytes.decode()
    session = await _get_session(session_id)

    return ResumeSessionResponse(
        session_id=session_id,
        planning=PlanningInfo(**session["planning"]),
        completed_attractions=session.get("completed_attractions", []),
        current_location=session.get("current_location"),
    )


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Return stored message history for a session (for client-side resume)."""
    await _get_session(session_id)  # verify session exists
    messages = await _get_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    session = await _get_session(request.session_id)
    messages = await _get_messages(request.session_id)

    # Block archived visits from receiving new AI messages
    try:
        async for db in get_db():
            visit = await db.get(ParkVisit, request.session_id)
            if visit and visit.status == "archived":
                raise HTTPException(status_code=403, detail="该游园记录已归档，无法继续对话")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("检查游园归档状态失败: %s", e)

    planning = PlanningInfo(**session["planning"])

    try:
        wait_times = await fetch_wait_times(planning.park_id)
        wt_json = wait_times_to_json(wait_times)
    except Exception as e:
        logger.warning("聊天流：排队数据获取失败: %s", e)
        wt_json = "{}"

    strategy_snippets: list[str] = []
    try:
        async for db in get_db():
            strategy_snippets = await get_strategy_snippets(
                db, planning.park_id,
                preferences=planning.preferences,
            )
    except Exception as e:
        logger.warning("聊天流：攻略摘要获取失败: %s", e)

    messages.append({"role": "user", "content": request.message})

    # 智能重规划：检测完成进度变化，必要时增强用户消息
    completed_attractions = session.get("completed_attractions", [])
    prev_completed = session.get("_prev_completed_count", 0)
    if len(completed_attractions) > prev_completed and len(completed_attractions) > 0:
        session["_prev_completed_count"] = len(completed_attractions)
        await _save_session(request.session_id, session)
        # 在用户消息中追加进度感知提示（不改变用户原始意图）
        progress_hint = (
            f"\n\n[系统提示] 用户已完成 {len(completed_attractions)} 个项目（"
            + "、".join(completed_attractions[-3:])
            + "），当前时间已推进。如果用户的行程需要调整，请主动建议重新规划后续路线。"
        )
        messages[-1]["content"] += progress_hint

    async def event_stream():
        accumulated = ""

        async for chunk in stream_chat_response(
            planning=planning,
            messages=messages,
            wait_times_json=wt_json,
            completed_attractions=completed_attractions,
            current_location=request.current_location,
            strategy_snippets=strategy_snippets,
            ai_config=request.ai_config,
        ):
            if chunk["type"] == "text":
                accumulated += chunk["content"]

            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        messages.append({"role": "assistant", "content": accumulated})
        await _save_messages(request.session_id, messages)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
