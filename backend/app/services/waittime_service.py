import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.redis_client import get_redis, is_redis_available
from app.schemas import WaitTimeItem, WaitTimesResponse

logger = logging.getLogger(__name__)

QUEUE_TIMES_PARK_IDS = {
    "shanghai_disney": 30,
    "hongkong_disney": 31,
}

QUEUE_TIMES_BASE = "https://queue-times.com/parks"

_DATA_DIR = Path(__file__).parent.parent / "data"


@lru_cache(maxsize=4)
def _load_ride_id_to_name(park_id: str) -> dict[str, str]:
    """Build a mapping of queue_times_ride_id → Chinese name from static JSON."""
    data_file = _DATA_DIR / f"{park_id}.json"
    if not data_file.exists():
        return {}
    try:
        data = json.loads(data_file.read_text(encoding="utf-8"))
        result: dict[str, str] = {}

        def _collect(items: list[dict]) -> None:
            for a in items:
                if a.get("queue_times_ride_id") and a.get("name"):
                    result[str(a["queue_times_ride_id"])] = a["name"]

        # Top-level areas[].attractions[]
        for area in data.get("areas", []):
            _collect(area.get("attractions", []))
        # Top-level shows_and_parades[]
        _collect(data.get("shows_and_parades", []))
        # Flat list fallback (shanghai format)
        if isinstance(data, list):
            _collect(data)

        return result
    except Exception as e:
        logger.warning("加载 %s 项目名称映射失败: %s", park_id, e)
        return {}


async def fetch_wait_times(park_id: str) -> WaitTimesResponse:
    now_iso = datetime.now(timezone.utc).isoformat()
    cache_key = f"waittimes:{park_id}"

    # Try Redis cache first (gracefully skip if Redis unavailable)
    if is_redis_available():
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)
            if cached:
                return WaitTimesResponse.model_validate_json(cached)
        except Exception as e:
            logger.warning("Redis 缓存读取失败 (%s): %s", park_id, e)

    qt_park_id = QUEUE_TIMES_PARK_IDS.get(park_id)
    if not qt_park_id:
        raise ValueError(f"Unknown park_id: {park_id}")

    url = f"{QUEUE_TIMES_BASE}/{qt_park_id}/queue_times.json"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("queue-times.com API 请求失败 (%s): %s", park_id, e)
        return WaitTimesResponse(park_id=park_id, last_updated=now_iso, attractions=[])

    # queue-times.com returns either lands[].rides[] or a flat rides[] depending on park
    raw_rides: list[dict] = []
    if data.get("lands"):
        for land in data["lands"]:
            raw_rides.extend(land.get("rides", []))
    else:
        raw_rides = data.get("rides", [])

    name_map = _load_ride_id_to_name(park_id)

    attractions: list[WaitTimeItem] = []
    for ride in raw_rides:
        is_open = ride.get("is_open", False)
        wait = ride.get("wait_time")
        ride_id = str(ride.get("id", ""))
        attractions.append(
            WaitTimeItem(
                attraction_id=ride_id,
                attraction_name=name_map.get(ride_id),
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

    # Try to cache result (gracefully skip if Redis unavailable)
    if is_redis_available():
        try:
            redis = await get_redis()
            await redis.setex(cache_key, settings.waittime_cache_ttl_seconds, result.model_dump_json())
        except Exception as e:
            logger.warning("Redis 缓存写入失败 (%s): %s", park_id, e)

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
