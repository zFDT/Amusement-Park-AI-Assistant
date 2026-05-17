import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.redis_client import get_redis
from app.core.database import get_db
from app.schemas import ChatRequest, CreateSessionRequest, CreateSessionResponse
from app.services.ai_service import generate_initial_plan, stream_chat_response
from app.services.waittime_service import fetch_wait_times, wait_times_to_json
from app.services.strategy_service import get_strategy_snippets

router = APIRouter()


async def _get_session(session_id: str) -> dict:
    redis = await get_redis()
    raw = await redis.get(f"session:{session_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return json.loads(raw)


async def _save_session(session_id: str, data: dict) -> None:
    redis = await get_redis()
    await redis.setex(
        f"session:{session_id}",
        settings.session_ttl_seconds,
        json.dumps(data, ensure_ascii=False),
    )


async def _get_messages(session_id: str) -> list[dict]:
    redis = await get_redis()
    raw = await redis.get(f"messages:{session_id}")
    return json.loads(raw) if raw else []


async def _save_messages(session_id: str, messages: list[dict]) -> None:
    redis = await get_redis()
    # Keep last 20 messages to avoid context overflow
    trimmed = messages[-20:]
    await redis.setex(
        f"messages:{session_id}",
        settings.session_ttl_seconds,
        json.dumps(trimmed, ensure_ascii=False),
    )


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    session_id = str(uuid.uuid4())

    try:
        wait_times = await fetch_wait_times(request.park_id)
        wt_json = wait_times_to_json(wait_times)
    except Exception:
        wt_json = "{}"

    strategy_snippets: list[str] = []
    try:
        async for db in get_db():
            strategy_snippets = await get_strategy_snippets(db, request.park_id)
    except Exception:
        pass

    initial_plan, route = await generate_initial_plan(request, wt_json, strategy_snippets)

    session_data = {
        "session_id": session_id,
        "planning": request.model_dump(),
        "completed_attractions": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _save_session(session_id, session_data)

    initial_message = {
        "role": "assistant",
        "content": initial_plan,
    }
    await _save_messages(session_id, [initial_message])

    return CreateSessionResponse(
        session_id=session_id,
        initial_plan=initial_plan,
        route=route,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    session = await _get_session(request.session_id)
    messages = await _get_messages(request.session_id)

    from app.schemas import PlanningInfo
    planning = PlanningInfo(**session["planning"])

    try:
        wait_times = await fetch_wait_times(planning.park_id)
        wt_json = wait_times_to_json(wait_times)
    except Exception:
        wt_json = "{}"

    strategy_snippets: list[str] = []
    try:
        async for db in get_db():
            strategy_snippets = await get_strategy_snippets(db, planning.park_id)
    except Exception:
        pass

    messages.append({"role": "user", "content": request.message})

    async def event_stream():
        accumulated = ""
        route_data = None

        async for chunk in stream_chat_response(
            planning=planning,
            messages=messages,
            wait_times_json=wt_json,
            completed_attractions=session.get("completed_attractions", []),
            current_location=request.current_location,
            strategy_snippets=strategy_snippets,
        ):
            if chunk["type"] == "text":
                accumulated += chunk["content"]
            elif chunk["type"] == "route_update":
                route_data = chunk["route"]

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
