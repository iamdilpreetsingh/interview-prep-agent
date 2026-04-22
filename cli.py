#!/usr/bin/env python3
"""Interactive CLI client for CrackCode interview prep agent."""

from __future__ import annotations

import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


async def setup_profile() -> int:
    """Interactive profile setup."""
    from app.database import User, async_session, init_db

    await init_db()

    console.print(
        Panel(
            "[bold]Welcome to CrackCode![/bold]\n"
            "Your AI interview coach for cracking SDE roles at top tech companies.\n"
            "Let's set up your profile first.",
            border_style="cyan",
        )
    )

    name = Prompt.ask("[cyan]Your name[/cyan]")
    target_company = Prompt.ask("[cyan]Target company[/cyan]", default="Zomato")
    target_role = Prompt.ask("[cyan]Target role[/cyan]", default="SDE-2")
    current_company = Prompt.ask("[cyan]Current company (optional)[/cyan]", default="")
    exp = Prompt.ask("[cyan]Years of experience[/cyan]", default="2")
    tech = Prompt.ask("[cyan]Tech stack (comma-separated)[/cyan]", default="Python, Java")
    strengths = Prompt.ask("[cyan]Strengths (comma-separated)[/cyan]", default="")
    weaknesses = Prompt.ask("[cyan]Areas to improve (comma-separated)[/cyan]", default="")
    hours = Prompt.ask("[cyan]Daily hours available for prep[/cyan]", default="2")
    study_time = Prompt.ask(
        "[cyan]Preferred study time[/cyan]",
        choices=["morning", "afternoon", "evening", "night"],
        default="evening",
    )

    async with async_session() as session:
        user = User(
            name=name,
            target_company=target_company,
            target_role=target_role,
            current_company=current_company or None,
            experience_years=float(exp),
            tech_stack=[s.strip() for s in tech.split(",") if s.strip()],
            strengths=[s.strip() for s in strengths.split(",") if s.strip()],
            weaknesses=[s.strip() for s in weaknesses.split(",") if s.strip()],
            daily_hours_available=float(hours),
            preferred_study_time=study_time,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        console.print(f"\n[green]Profile created! Your user ID is {user.id}[/green]\n")
        return user.id


async def main():
    from dotenv import load_dotenv

    load_dotenv()

    from app.database import User, async_session, init_db

    await init_db()

    # Check for existing user or create new
    user_id = None
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
    else:
        async with async_session() as session:
            from sqlalchemy import select

            result = await session.execute(select(User).limit(1))
            user = result.scalar_one_or_none()
            if user:
                user_id = user.id
                console.print(
                    f"[dim]Resuming as {user.name} (ID: {user.id}) "
                    f"| Target: {user.target_role} @ {user.target_company}[/dim]\n"
                )

    if not user_id:
        user_id = await setup_profile()

    from app.agent import chat

    console.print(
        Panel(
            "[bold cyan]CrackCode[/bold cyan] is ready. Type your message below.\n"
            "Commands: [dim]/quit[/dim] to exit, [dim]/profile[/dim] to view profile, "
            "[dim]/progress[/dim] to see scores, [dim]/goals[/dim] to see goals",
            border_style="cyan",
        )
    )

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye! Keep grinding.[/dim]")
            break

        if not user_input.strip():
            continue

        if user_input.strip() == "/quit":
            console.print("[dim]Goodbye! Keep grinding.[/dim]")
            break

        if user_input.strip() == "/profile":
            from app.tools import get_user_profile

            data = json.loads(await get_user_profile(user_id))
            console.print(Panel(json.dumps(data, indent=2), title="Your Profile"))
            continue

        if user_input.strip() == "/progress":
            from app.tools import get_user_progress

            data = json.loads(await get_user_progress(user_id))
            console.print(Panel(json.dumps(data, indent=2), title="Your Progress"))
            continue

        if user_input.strip() == "/goals":
            from app.tools import get_goals

            data = json.loads(await get_goals(user_id))
            console.print(Panel(json.dumps(data, indent=2), title="Your Goals"))
            continue

        # Send to agent
        with console.status("[cyan]Thinking...[/cyan]", spinner="dots"):
            try:
                reply, tools_used = await chat(user_id, user_input)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                continue

        if tools_used:
            console.print(f"[dim]Tools used: {', '.join(tools_used)}[/dim]")

        console.print()
        console.print(Panel(Markdown(reply), title="[bold cyan]CrackCode[/bold cyan]", border_style="cyan"))


if __name__ == "__main__":
    asyncio.run(main())
