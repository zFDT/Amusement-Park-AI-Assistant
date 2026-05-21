"""双园对比接口 —— 对比香港和上海迪士尼的关键指标。"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.database import get_db
from app.models.park import Park, Attraction, Strategy
from app.services.waittime_service import fetch_wait_times, wait_times_to_json
from sqlalchemy import select, func

router = APIRouter(prefix="/compare", tags=["compare"])


class ParkSummary(BaseModel):
    park_id: str
    park_name: str
    attraction_count: int
    thrill_ride_count: int
    family_ride_count: int
    show_count: int
    strategy_count: int
    average_wait: int | None
    hottest_attraction: str | None
    hottest_wait: int | None


class CompareResponse(BaseModel):
    parks: list[ParkSummary]
    recommendation: str


@router.get("", response_model=CompareResponse)
async def compare_parks():
    """返回香港和上海迪士尼的关键对比指标。"""
    parks = []
    for park_id in ("hongkong_disney", "shanghai_disney"):
        summary = await _build_park_summary(park_id)
        if summary:
            parks.append(summary)

    # 生成推荐
    recommendation = _generate_recommendation(parks)

    return CompareResponse(parks=parks, recommendation=recommendation)


async def _build_park_summary(park_id: str) -> ParkSummary | None:
    async for db in get_db():
        # 乐园基本信息
        park_result = await db.execute(select(Park).where(Park.id == park_id))
        park = park_result.scalar()
        if not park:
            return None

        # 项目统计
        attr_result = await db.execute(
            select(Attraction).where(Attraction.park_id == park_id, Attraction.is_active == True)
        )
        attractions = attr_result.scalars().all()

        thrill = sum(1 for a in attractions if a.category == "thrill_ride")
        family = sum(1 for a in attractions if a.category == "family_ride")
        shows = sum(1 for a in attractions if a.category == "show")

        # 攻略统计
        strategy_count_result = await db.execute(
            select(func.count()).select_from(Strategy).where(
                Strategy.park_id == park_id, Strategy.is_active == True
            )
        )
        strategy_count = int(strategy_count_result.scalar() or 0)

        # 实时排队数据
        average_wait = None
        hottest_attraction = None
        hottest_wait = None
        try:
            wait_times = await fetch_wait_times(park_id)
            waits = [wt.wait_minutes for wt in wait_times if wt.wait_minutes is not None]
            if waits:
                average_wait = sum(waits) // len(waits)
            hottest = max(wait_times, key=lambda wt: wt.wait_minutes or 0, default=None)
            if hottest and hottest.wait_minutes:
                hottest_attraction = hottest.attraction_name or f"Ride {hottest.attraction_id}"
                hottest_wait = hottest.wait_minutes
        except Exception:
            pass

        return ParkSummary(
            park_id=park_id,
            park_name=park.name,
            attraction_count=len(attractions),
            thrill_ride_count=thrill,
            family_ride_count=family,
            show_count=shows,
            strategy_count=strategy_count,
            average_wait=average_wait,
            hottest_attraction=hottest_attraction,
            hottest_wait=hottest_wait,
        )


def _generate_recommendation(parks: list[ParkSummary]) -> str:
    if len(parks) < 2:
        return "数据不足，无法生成对比建议"

    hk = next((p for p in parks if p.park_id == "hongkong_disney"), None)
    sh = next((p for p in parks if p.park_id == "shanghai_disney"), None)

    if not hk or not sh:
        return "数据不足，无法生成对比建议"

    lines = []
    lines.append(f"香港迪士尼有 {hk.attraction_count} 个项目，上海迪士尼有 {sh.attraction_count} 个项目。")

    if hk.average_wait and sh.average_wait:
        if hk.average_wait < sh.average_wait:
            lines.append(f"当前香港平均排队 {hk.average_wait} 分钟，低于上海的 {sh.average_wait} 分钟。")
        else:
            lines.append(f"当前上海平均排队 {sh.average_wait} 分钟，低于香港的 {hk.average_wait} 分钟。")

    if hk.strategy_count > sh.strategy_count:
        lines.append(f"香港迪士尼有 {hk.strategy_count} 条攻略参考，略多于上海（{sh.strategy_count} 条）。")
    else:
        lines.append(f"上海迪士尼有 {sh.strategy_count} 条攻略参考，略多于香港（{hk.strategy_count} 条）。")

    # 特色建议
    lines.append("香港迪士尼更紧凑精致，适合首次游园和亲子出行；上海迪士尼规模更大，适合追求刺激项目和丰富体验的游客。")

    return " ".join(lines)
