"""Conversation memory management — load/save history for context continuity."""

from __future__ import annotations

from sqlalchemy import select

from app.database import Conversation, async_session

# Max messages to load as context (keeps token usage reasonable)
MAX_HISTORY = 40


async def load_history(user_id: int) -> list[dict]:
    """Load recent conversation history for a user as Claude message format."""
    async with async_session() as session:
        rows = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(MAX_HISTORY)
        )
        messages = rows.scalars().all()

    # Reverse to chronological order
    messages = list(reversed(messages))

    return [{"role": m.role, "content": m.content} for m in messages]


async def save_message(user_id: int, role: str, content: str) -> None:
    """Persist a single message to the conversation history."""
    async with async_session() as session:
        session.add(Conversation(user_id=user_id, role=role, content=content))
        await session.commit()


async def get_conversation_count(user_id: int) -> int:
    """Get total number of messages for a user."""
    async with async_session() as session:
        from sqlalchemy import func

        result = await session.execute(
            select(func.count()).where(Conversation.user_id == user_id)
        )
        return result.scalar_one()
