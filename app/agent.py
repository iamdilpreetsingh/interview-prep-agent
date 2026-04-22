"""Core agent loop — handles the conversation cycle with Claude and tool execution."""

from __future__ import annotations

import anthropic

from app.config import settings
from app.memory import load_history, save_message
from app.prompts import build_system_prompt
from app.tools import TOOL_DEFINITIONS, execute_tool, get_user_profile, get_user_progress

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# Max tool-use iterations per turn to prevent runaway loops
MAX_TOOL_ROUNDS = 10


async def chat(user_id: int, user_message: str) -> tuple[str, list[str]]:
    """
    Process a user message through the agent.

    Returns (assistant_reply, list_of_tools_used).
    """
    # 1. Load user context for system prompt enrichment
    user_ctx = await get_user_profile(user_id)
    progress_ctx = await get_user_progress(user_id)
    system_prompt = build_system_prompt(user_ctx, progress_ctx)

    # 2. Load conversation history
    history = await load_history(user_id)

    # 3. Append the new user message
    history.append({"role": "user", "content": user_message})

    # 4. Save user message to DB
    await save_message(user_id, "user", user_message)

    # 5. Run the agent loop (message -> tool calls -> results -> repeat)
    tools_used: list[str] = []
    messages = history.copy()

    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Check if we need to handle tool use
        if response.stop_reason == "tool_use":
            # Collect all tool calls from this response
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tools_used.append(block.name)
                    result = await execute_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})
        else:
            # Final text response
            reply_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    reply_text += block.text

            # Save assistant reply
            await save_message(user_id, "assistant", reply_text)

            return reply_text, tools_used

    # Safety: if we hit max rounds, return whatever we have
    return "I got a bit caught up in research. Could you repeat that?", tools_used


async def chat_stream(user_id: int, user_message: str):
    """
    Streaming version of chat. Yields text chunks as they arrive.

    Note: Tool use is handled internally; only final text is streamed.
    """
    # Load context
    user_ctx = await get_user_profile(user_id)
    progress_ctx = await get_user_progress(user_id)
    system_prompt = build_system_prompt(user_ctx, progress_ctx)

    history = await load_history(user_id)
    history.append({"role": "user", "content": user_message})
    await save_message(user_id, "user", user_message)

    messages = history.copy()
    tools_used: list[str] = []

    # Handle tool-use rounds non-streaming first
    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tools_used.append(block.name)
                    result = await execute_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # Now stream the final response
    full_text = ""
    async with client.messages.stream(
        model=settings.claude_model,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
        # No tools on the final streaming call to ensure pure text
    ) as stream:
        async for text in stream.text_stream:
            full_text += text
            yield text

    await save_message(user_id, "assistant", full_text)
