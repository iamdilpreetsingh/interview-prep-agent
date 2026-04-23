import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func

from app.database import DailyPlan, DailyTask, TaskComment, async_session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class TaskToggle(BaseModel):
    completed: bool


class CommentCreate(BaseModel):
    content: str


@router.get("/{user_id}/overview")
async def get_overview(user_id: int):
    """Get all daily plans with task completion summary."""
    async with async_session() as session:
        plans = await session.execute(
            select(DailyPlan)
            .where(DailyPlan.user_id == user_id)
            .order_by(DailyPlan.day_number)
        )
        result = []
        for plan in plans.scalars().all():
            tasks = await session.execute(
                select(DailyTask).where(DailyTask.plan_id == plan.id)
            )
            all_tasks = tasks.scalars().all()
            total = len(all_tasks)
            done = sum(1 for t in all_tasks if t.completed)
            result.append({
                "id": plan.id,
                "day_number": plan.day_number,
                "date": plan.date,
                "week_number": plan.week_number,
                "phase": plan.phase,
                "status": plan.status,
                "total_tasks": total,
                "completed_tasks": done,
                "progress_pct": round(done / total * 100) if total else 0,
            })
    return {"plans": result}


@router.get("/{user_id}/day/{day_number}")
async def get_day(user_id: int, day_number: int):
    """Get a specific day's plan with all tasks and comments."""
    async with async_session() as session:
        plan = await session.execute(
            select(DailyPlan).where(
                DailyPlan.user_id == user_id, DailyPlan.day_number == day_number
            )
        )
        plan = plan.scalar_one_or_none()
        if not plan:
            raise HTTPException(404, "Plan not found for this day")

        tasks = await session.execute(
            select(DailyTask)
            .where(DailyTask.plan_id == plan.id)
            .order_by(DailyTask.order)
        )

        task_list = []
        for t in tasks.scalars().all():
            comments = await session.execute(
                select(TaskComment)
                .where(TaskComment.task_id == t.id)
                .order_by(TaskComment.created_at)
            )
            task_list.append({
                "id": t.id,
                "session": t.session,
                "title": t.title,
                "description": t.description,
                "resources": t.resources,
                "success_metric": t.success_metric,
                "pitfalls": t.pitfalls,
                "duration_minutes": t.duration_minutes,
                "completed": t.completed,
                "order": t.order,
                "comments": [
                    {"id": c.id, "content": c.content, "created_at": c.created_at.isoformat()}
                    for c in comments.scalars().all()
                ],
            })

    return {
        "plan": {
            "id": plan.id,
            "day_number": plan.day_number,
            "date": plan.date,
            "week_number": plan.week_number,
            "phase": plan.phase,
            "status": plan.status,
        },
        "tasks": task_list,
    }


@router.patch("/tasks/{task_id}")
async def toggle_task(task_id: int, body: TaskToggle):
    """Toggle a task's completion status."""
    async with async_session() as session:
        task = await session.get(DailyTask, task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        task.completed = body.completed
        await session.commit()
    return {"status": "ok", "task_id": task_id, "completed": body.completed}


@router.post("/tasks/{task_id}/comments")
async def add_comment(task_id: int, body: CommentCreate):
    """Add a comment to a task."""
    async with async_session() as session:
        task = await session.get(DailyTask, task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        comment = TaskComment(
            task_id=task_id,
            user_id=task.user_id,
            content=body.content,
        )
        session.add(comment)
        await session.commit()
        await session.refresh(comment)
    return {"id": comment.id, "content": comment.content, "created_at": comment.created_at.isoformat()}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: int):
    """Delete a comment."""
    async with async_session() as session:
        comment = await session.get(TaskComment, comment_id)
        if not comment:
            raise HTTPException(404, "Comment not found")
        await session.delete(comment)
        await session.commit()
    return {"status": "deleted"}
