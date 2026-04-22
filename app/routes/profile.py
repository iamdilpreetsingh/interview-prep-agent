from fastapi import APIRouter, HTTPException

from app.database import User, async_session
from app.schemas import UserProfileCreate, UserProfileOut

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("", response_model=UserProfileOut)
async def create_profile(data: UserProfileCreate):
    async with async_session() as session:
        user = User(
            name=data.name,
            target_company=data.target_company,
            target_role=data.target_role,
            current_company=data.current_company,
            experience_years=data.experience_years,
            tech_stack=data.tech_stack,
            strengths=data.strengths,
            weaknesses=data.weaknesses,
            daily_hours_available=data.daily_hours_available,
            preferred_study_time=data.preferred_study_time,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@router.get("/{user_id}", response_model=UserProfileOut)
async def get_profile(user_id: int):
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        return user


@router.put("/{user_id}", response_model=UserProfileOut)
async def update_profile(user_id: int, data: UserProfileCreate):
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await session.commit()
        await session.refresh(user)
        return user
