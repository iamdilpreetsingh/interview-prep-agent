import json

from fastapi import APIRouter

from app.schemas import GoalCreate, GoalOut
from app.tools import get_goals as _get_goals
from app.tools import get_study_plan as _get_plan
from app.tools import get_user_progress as _get_progress
from app.tools import set_goal as _set_goal

router = APIRouter(tags=["goals & progress"])


@router.get("/goals/{user_id}")
async def list_goals(user_id: int, status: str | None = None):
    raw = await _get_goals(user_id, status)
    return json.loads(raw)


@router.post("/goals/{user_id}")
async def create_goal(user_id: int, data: GoalCreate):
    raw = await _set_goal(
        user_id,
        data.title,
        data.description,
        data.target_date.isoformat() if data.target_date else None,
        data.priority,
    )
    return json.loads(raw)


@router.get("/progress/{user_id}")
async def get_progress(user_id: int):
    raw = await _get_progress(user_id)
    return json.loads(raw)


@router.get("/plan/{user_id}")
async def get_plan(user_id: int, week: int | None = None):
    raw = await _get_plan(user_id, week)
    return json.loads(raw)
