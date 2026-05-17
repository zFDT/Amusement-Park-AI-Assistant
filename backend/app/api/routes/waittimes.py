from fastapi import APIRouter, HTTPException

from app.schemas import WaitTimesResponse
from app.services.waittime_service import fetch_wait_times

router = APIRouter()


@router.get("/waittimes/{park_id}", response_model=WaitTimesResponse)
async def get_wait_times(park_id: str):
    try:
        return await fetch_wait_times(park_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch wait times: {e}")
