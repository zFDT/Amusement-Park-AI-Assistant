"""用户登录（昵称即身份）和游园记录管理"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.park import User, ParkVisit
from app.schemas import (
    LoginRequest,
    LoginResponse,
    VisitSummary,
    VisitListResponse,
    ArchiveVisitResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """昵称即身份：存在则返回用户信息，不存在则自动注册。"""
    uid = request.user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="用户标识不能为空")
    if len(uid) > 50:
        raise HTTPException(status_code=400, detail="用户标识不能超过50个字符")

    async for db in get_db():
        user = await db.get(User, uid)
        is_new = user is None
        if is_new:
            user = User(id=uid)
            db.add(user)
            await db.commit()
        else:
            from datetime import datetime, timezone
            user.last_seen_at = datetime.now(timezone.utc)
            await db.commit()

        return LoginResponse(user_id=uid, is_new=is_new)


@router.get("/{user_id}/visits", response_model=VisitListResponse)
async def list_visits(user_id: str):
    """返回该用户所有游园记录，按创建时间倒序。"""
    async for db in get_db():
        result = await db.execute(
            select(ParkVisit)
            .where(ParkVisit.user_id == user_id)
            .order_by(ParkVisit.created_at.desc())
        )
        visits = result.scalars().all()

        summaries = [
            VisitSummary(
                visit_id=v.id,
                park_id=v.park_id,
                visit_date=v.visit_date or "",
                status=v.status,
                completed_count=len(v.completed_attractions or []),
                created_at=v.created_at.isoformat(),
                planning_snapshot=v.planning_snapshot,
            )
            for v in visits
        ]
        return VisitListResponse(user_id=user_id, visits=summaries)


@router.patch("/{user_id}/visits/{visit_id}/archive", response_model=ArchiveVisitResponse)
async def archive_visit(user_id: str, visit_id: str):
    """归档一次游园：保留数据，标记为 archived，不再提供 AI 对话。"""
    async for db in get_db():
        visit = await db.get(ParkVisit, visit_id)
        if not visit or visit.user_id != user_id:
            raise HTTPException(status_code=404, detail="游园记录不存在")
        if visit.status == "archived":
            return ArchiveVisitResponse(visit_id=visit_id, status="archived")

        visit.status = "archived"
        await db.commit()
        return ArchiveVisitResponse(visit_id=visit_id, status="archived")
