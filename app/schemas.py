from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


# --- User Profile ---


class UserProfileCreate(BaseModel):
    name: str
    target_company: str = "Zomato"
    target_role: str = "SDE-2"
    current_company: str | None = None
    experience_years: float = 0
    tech_stack: list[str] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    daily_hours_available: float = 2.0
    preferred_study_time: str = "evening"  # morning / afternoon / evening / night


class UserProfileOut(UserProfileCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Chat ---


class ChatRequest(BaseModel):
    user_id: int = 1
    message: str


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str] = []


# --- Goals ---


class GoalStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    target_date: date | None = None
    priority: int = 1  # 1=highest


class GoalOut(GoalCreate):
    id: int
    user_id: int
    status: GoalStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Progress ---


class TopicScore(BaseModel):
    topic: str
    subtopic: str = ""
    score: int  # 0-100
    notes: str = ""


class ProgressOut(TopicScore):
    id: int
    user_id: int
    assessed_at: datetime

    model_config = {"from_attributes": True}


# --- Study Plan ---


class StudyBlock(BaseModel):
    day: str  # Monday, Tuesday, ...
    time_slot: str
    topic: str
    duration_minutes: int = 60
    resources: str = ""


class StudyPlanOut(StudyBlock):
    id: int
    user_id: int
    week_number: int
    completed: bool

    model_config = {"from_attributes": True}
