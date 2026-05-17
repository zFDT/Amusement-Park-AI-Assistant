import json
import random
import string
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.redis_client import get_redis
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
from app.services.ai_service import generate_initial_plan, stream_chat_response
from app.services.waittime_service import fetch_wait_times, wait_times_to_json
from app.services.strategy_service import get_strategy_snippets

router = APIRouter()

_SHARE_CODE_TTL = 7 * 24 * 3600  # 7 days


def _generate_share_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


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

    initial_plan, route = await generate_initial_plan(
        request, wt_json, strategy_snippets, ai_config=request.ai_config
    )

    session_data = {
        "session_id": session_id,
        "planning": request.model_dump(),
        "completed_attractions": [],
        "current_location": None,
        "user_id": request.user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _save_session(session_id, session_data)

    initial_message = {
        "role": "assistant",
        "content": initial_plan,
    }
    await _save_messages(session_id, [initial_message])

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
            pass  # DB write failure doesn't block the session

    return CreateSessionResponse(
        session_id=session_id,
        initial_plan=initial_plan,
        route=route,
    )


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
    except Exception:
        pass

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

        async for chunk in stream_chat_response(
            planning=planning,
            messages=messages,
            wait_times_json=wt_json,
            completed_attractions=session.get("completed_attractions", []),
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
