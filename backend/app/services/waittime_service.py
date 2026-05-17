import json
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.redis_client import get_redis
from app.schemas import WaitTimeItem, WaitTimesResponse

QUEUE_TIMES_PARK_IDS = {
    "shanghai_disney": 30,
    "hongkong_disney": 31,
}

QUEUE_TIMES_BASE = "https://queue-times.com/parks"


async def fetch_wait_times(park_id: str) -> WaitTimesResponse:
    redis = await get_redis()
    cache_key = f"waittimes:{park_id}"

    cached = await redis.get(cache_key)
    if cached:
        return WaitTimesResponse.model_validate_json(cached)

    qt_park_id = QUEUE_TIMES_PARK_IDS.get(park_id)
    if not qt_park_id:
        raise ValueError(f"Unknown park_id: {park_id}")

    url = f"{QUEUE_TIMES_BASE}/{qt_park_id}/queue_times.json"
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return WaitTimesResponse(park_id=park_id, last_updated=now_iso, attractions=[])

    # queue-times.com returns either lands[].rides[] or a flat rides[] depending on park
    raw_rides: list[dict] = []
    if data.get("lands"):
        for land in data["lands"]:
            raw_rides.extend(land.get("rides", []))
    else:
        raw_rides = data.get("rides", [])

    attractions: list[WaitTimeItem] = []
    for ride in raw_rides:
        is_open = ride.get("is_open", False)
        wait = ride.get("wait_time")
        attractions.append(
            WaitTimeItem(
                attraction_id=str(ride.get("id", "")),
                wait_minutes=int(wait) if wait is not None and is_open else None,
                status="open" if is_open else "closed",
                last_updated=now_iso,
            )
        )

    result = WaitTimesResponse(
        park_id=park_id,
        last_updated=now_iso,
        attractions=attractions,
    )

    await redis.setex(cache_key, settings.waittime_cache_ttl_seconds, result.model_dump_json())
    return result


def wait_times_to_json(response: WaitTimesResponse) -> str:
    simplified = {
        item.attraction_id: {
            "wait": item.wait_minutes,
            "status": item.status,
        }
        for item in response.attractions
    }
    return json.dumps(simplified, ensure_ascii=False)
