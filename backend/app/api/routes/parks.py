import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data"

PARK_DATA_FILES = {
    "shanghai_disney": DATA_DIR / "shanghai_disney.json",
    "hongkong_disney": DATA_DIR / "hongkong_disney.json",
}


@router.get("/parks/{park_id}/attractions")
async def get_attractions(park_id: str):
    data_file = PARK_DATA_FILES.get(park_id)
    if not data_file or not data_file.exists():
        raise HTTPException(status_code=404, detail=f"Park data not found: {park_id}")
    return json.loads(data_file.read_text(encoding="utf-8"))


@router.get("/parks")
async def list_parks():
    return [
        {"id": "hongkong_disney", "name": "香港迪士尼乐园", "available": True},
        {"id": "shanghai_disney", "name": "上海迪士尼乐园", "available": False, "note": "即将上线"},
    ]
