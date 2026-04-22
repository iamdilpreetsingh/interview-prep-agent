"""Tool definitions and implementations for the interview prep agent."""

from __future__ import annotations

import json
from datetime import datetime

import httpx
from sqlalchemy import select, update

from app.config import settings
from app.database import (
    Conversation,
    Goal,
    Progress,
    ResearchCache,
    StudyPlan,
    User,
    async_session,
)

# ── Claude Tool Definitions ─────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_web",
        "description": (
            "Search the internet for recent interview experiences, company information, "
            "hiring news, blog posts, and interview questions. Use this to gather real, "
            "up-to-date data about target companies and their interview processes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'Zomato SDE-2 interview experience 2025'",
                },
                "company": {
                    "type": "string",
                    "description": "Company name for caching purposes",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_user_profile",
        "description": (
            "Retrieve the user's full profile including name, target company, role, "
            "tech stack, strengths, weaknesses, available study hours, and preferences."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "The user's ID"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_user_progress",
        "description": (
            "Get the user's progress scores across all topics. Returns a list of "
            "topics with their latest scores (0-100) and notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "update_user_progress",
        "description": (
            "Update the user's score on a specific topic/subtopic after evaluating "
            "their practice or assessing their knowledge. Score is 0-100."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "topic": {
                    "type": "string",
                    "description": "Main topic: DSA, System Design, LLD, Behavioral, etc.",
                },
                "subtopic": {
                    "type": "string",
                    "description": "Specific area: Arrays, Trees, DP, Order Management, etc.",
                },
                "score": {
                    "type": "integer",
                    "description": "Score from 0-100",
                    "minimum": 0,
                    "maximum": 100,
                },
                "notes": {
                    "type": "string",
                    "description": "Assessment notes — what went well, what to improve",
                },
            },
            "required": ["user_id", "topic", "subtopic", "score"],
        },
    },
    {
        "name": "get_goals",
        "description": "Get all goals for the user, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "skipped"],
                    "description": "Filter by status. Omit to get all goals.",
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "set_goal",
        "description": (
            "Create a new goal or update an existing goal's status. "
            "Goals track what the user is working toward."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "target_date": {
                    "type": "string",
                    "description": "Target date in YYYY-MM-DD format",
                },
                "priority": {
                    "type": "integer",
                    "description": "1 = highest priority",
                    "minimum": 1,
                    "maximum": 5,
                },
                "goal_id": {
                    "type": "integer",
                    "description": "If provided, updates this goal instead of creating new",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "skipped"],
                },
            },
            "required": ["user_id", "title"],
        },
    },
    {
        "name": "get_study_plan",
        "description": "Retrieve the user's current study plan for a specific week.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "week_number": {
                    "type": "integer",
                    "description": "Week number (1-based). Omit for current week.",
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "save_study_plan",
        "description": (
            "Save a structured weekly study plan. Each block has a day, time slot, "
            "topic, duration, and optional resources."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "week_number": {"type": "integer"},
                "blocks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day": {"type": "string"},
                            "time_slot": {"type": "string"},
                            "topic": {"type": "string"},
                            "duration_minutes": {"type": "integer"},
                            "resources": {"type": "string"},
                        },
                        "required": ["day", "time_slot", "topic"],
                    },
                },
            },
            "required": ["user_id", "week_number", "blocks"],
        },
    },
    {
        "name": "save_research",
        "description": "Cache company research results to avoid redundant searches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "query": {"type": "string"},
                "result": {"type": "string"},
            },
            "required": ["company", "query", "result"],
        },
    },
]


# ── Tool Implementations ────────────────────────────────────────────────────


async def search_web(query: str, company: str = "") -> str:
    """Search the web using Tavily API, falling back to DuckDuckGo."""
    # Try cached results first
    if company:
        async with async_session() as session:
            cached = await session.execute(
                select(ResearchCache)
                .where(ResearchCache.company == company, ResearchCache.query == query)
                .order_by(ResearchCache.fetched_at.desc())
                .limit(1)
            )
            row = cached.scalar_one_or_none()
            if row:
                age_hours = (datetime.utcnow() - row.fetched_at).total_seconds() / 3600
                if age_hours < 72:  # Cache for 3 days
                    return row.result

    # Try Tavily first
    if settings.tavily_api_key:
        try:
            return await _search_tavily(query, company)
        except Exception:
            pass

    # Fallback to DuckDuckGo HTML
    return await _search_ddg(query, company)


async def _search_tavily(query: str, company: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 8,
                "include_raw_content": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for r in data.get("results", []):
        results.append(f"**{r['title']}**\n{r['url']}\n{r.get('content', '')}\n")

    text = "\n---\n".join(results) if results else "No results found."

    # Cache
    if company:
        await _cache_research(company, query, text)

    return text


async def _search_ddg(query: str, company: str) -> str:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; InterviewPrepAgent/1.0)"},
        )

    results = []
    # Simple extraction from DDG HTML response
    text = resp.text
    # Extract result snippets between class="result__snippet"
    import re

    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</a', text, re.DOTALL
    )
    titles = re.findall(
        r'class="result__a"[^>]*>(.*?)</a', text, re.DOTALL
    )
    urls = re.findall(
        r'class="result__url"[^>]*>(.*?)</a', text, re.DOTALL
    )

    for i in range(min(len(snippets), 8)):
        title = re.sub(r"<[^>]+>", "", titles[i]) if i < len(titles) else ""
        url = re.sub(r"<[^>]+>", "", urls[i]).strip() if i < len(urls) else ""
        snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
        results.append(f"**{title}**\n{url}\n{snippet}\n")

    result_text = "\n---\n".join(results) if results else "No results found."

    if company:
        await _cache_research(company, query, result_text)

    return result_text


async def _cache_research(company: str, query: str, result: str) -> None:
    async with async_session() as session:
        session.add(ResearchCache(company=company, query=query, result=result))
        await session.commit()


async def get_user_profile(user_id: int) -> str:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return json.dumps({"error": "User not found. Ask them to set up their profile."})
        return json.dumps(
            {
                "id": user.id,
                "name": user.name,
                "target_company": user.target_company,
                "target_role": user.target_role,
                "current_company": user.current_company,
                "experience_years": user.experience_years,
                "tech_stack": user.tech_stack,
                "strengths": user.strengths,
                "weaknesses": user.weaknesses,
                "daily_hours_available": user.daily_hours_available,
                "preferred_study_time": user.preferred_study_time,
            }
        )


async def get_user_progress(user_id: int) -> str:
    async with async_session() as session:
        rows = await session.execute(
            select(Progress)
            .where(Progress.user_id == user_id)
            .order_by(Progress.topic, Progress.subtopic)
        )
        items = rows.scalars().all()
        if not items:
            return json.dumps({"progress": [], "note": "No progress recorded yet."})
        return json.dumps(
            {
                "progress": [
                    {
                        "topic": p.topic,
                        "subtopic": p.subtopic,
                        "score": p.score,
                        "notes": p.notes,
                        "assessed_at": p.assessed_at.isoformat(),
                    }
                    for p in items
                ]
            }
        )


async def update_user_progress(
    user_id: int, topic: str, subtopic: str, score: int, notes: str = ""
) -> str:
    async with async_session() as session:
        # Check for existing entry
        existing = await session.execute(
            select(Progress).where(
                Progress.user_id == user_id,
                Progress.topic == topic,
                Progress.subtopic == subtopic,
            )
        )
        row = existing.scalar_one_or_none()

        if row:
            row.score = score
            row.notes = notes
            row.assessed_at = datetime.utcnow()
        else:
            session.add(
                Progress(
                    user_id=user_id,
                    topic=topic,
                    subtopic=subtopic,
                    score=score,
                    notes=notes,
                )
            )
        await session.commit()
    return json.dumps({"status": "ok", "topic": topic, "subtopic": subtopic, "score": score})


async def get_goals(user_id: int, status: str | None = None) -> str:
    async with async_session() as session:
        q = select(Goal).where(Goal.user_id == user_id)
        if status:
            q = q.where(Goal.status == status)
        q = q.order_by(Goal.priority, Goal.created_at)
        rows = await session.execute(q)
        goals = rows.scalars().all()
        return json.dumps(
            {
                "goals": [
                    {
                        "id": g.id,
                        "title": g.title,
                        "description": g.description,
                        "target_date": g.target_date,
                        "priority": g.priority,
                        "status": g.status,
                    }
                    for g in goals
                ]
            }
        )


async def set_goal(
    user_id: int,
    title: str,
    description: str = "",
    target_date: str | None = None,
    priority: int = 1,
    goal_id: int | None = None,
    status: str | None = None,
) -> str:
    async with async_session() as session:
        if goal_id:
            goal = await session.get(Goal, goal_id)
            if goal:
                if status:
                    goal.status = status
                if title:
                    goal.title = title
                if description:
                    goal.description = description
                await session.commit()
                return json.dumps({"status": "updated", "goal_id": goal.id})
            return json.dumps({"error": "Goal not found"})

        goal = Goal(
            user_id=user_id,
            title=title,
            description=description,
            target_date=target_date,
            priority=priority,
        )
        session.add(goal)
        await session.commit()
        await session.refresh(goal)
        return json.dumps({"status": "created", "goal_id": goal.id})


async def get_study_plan(user_id: int, week_number: int | None = None) -> str:
    async with async_session() as session:
        q = select(StudyPlan).where(StudyPlan.user_id == user_id)
        if week_number:
            q = q.where(StudyPlan.week_number == week_number)
        else:
            # Get latest week
            latest = await session.execute(
                select(StudyPlan.week_number)
                .where(StudyPlan.user_id == user_id)
                .order_by(StudyPlan.week_number.desc())
                .limit(1)
            )
            wk = latest.scalar_one_or_none()
            if wk:
                q = q.where(StudyPlan.week_number == wk)

        q = q.order_by(StudyPlan.day, StudyPlan.time_slot)
        rows = await session.execute(q)
        blocks = rows.scalars().all()

        if not blocks:
            return json.dumps({"plan": [], "note": "No study plan yet. Ask me to create one!"})

        return json.dumps(
            {
                "week_number": blocks[0].week_number if blocks else 0,
                "plan": [
                    {
                        "day": b.day,
                        "time_slot": b.time_slot,
                        "topic": b.topic,
                        "duration_minutes": b.duration_minutes,
                        "resources": b.resources,
                        "completed": b.completed,
                    }
                    for b in blocks
                ],
            }
        )


async def save_study_plan(user_id: int, week_number: int, blocks: list[dict]) -> str:
    async with async_session() as session:
        # Clear existing plan for this week
        existing = await session.execute(
            select(StudyPlan).where(
                StudyPlan.user_id == user_id, StudyPlan.week_number == week_number
            )
        )
        for row in existing.scalars().all():
            await session.delete(row)

        # Insert new blocks
        for b in blocks:
            session.add(
                StudyPlan(
                    user_id=user_id,
                    week_number=week_number,
                    day=b["day"],
                    time_slot=b.get("time_slot", ""),
                    topic=b["topic"],
                    duration_minutes=b.get("duration_minutes", 60),
                    resources=b.get("resources", ""),
                )
            )
        await session.commit()
    return json.dumps({"status": "ok", "week": week_number, "blocks_saved": len(blocks)})


async def save_research(company: str, query: str, result: str) -> str:
    await _cache_research(company, query, result)
    return json.dumps({"status": "cached"})


# ── Tool Dispatcher ─────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "search_web": lambda args: search_web(args["query"], args.get("company", "")),
    "get_user_profile": lambda args: get_user_profile(args["user_id"]),
    "get_user_progress": lambda args: get_user_progress(args["user_id"]),
    "update_user_progress": lambda args: update_user_progress(
        args["user_id"], args["topic"], args["subtopic"], args["score"], args.get("notes", "")
    ),
    "get_goals": lambda args: get_goals(args["user_id"], args.get("status")),
    "set_goal": lambda args: set_goal(
        args["user_id"],
        args["title"],
        args.get("description", ""),
        args.get("target_date"),
        args.get("priority", 1),
        args.get("goal_id"),
        args.get("status"),
    ),
    "get_study_plan": lambda args: get_study_plan(args["user_id"], args.get("week_number")),
    "save_study_plan": lambda args: save_study_plan(
        args["user_id"], args["week_number"], args["blocks"]
    ),
    "save_research": lambda args: save_research(args["company"], args["query"], args["result"]),
}


async def execute_tool(name: str, args: dict) -> str:
    """Execute a tool by name and return the result string."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return await handler(args)
