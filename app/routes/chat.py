from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent import chat, chat_stream
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(req: ChatRequest):
    reply, tools_used = await chat(req.user_id, req.message)
    return ChatResponse(reply=reply, tools_used=tools_used)


@router.post("/stream")
async def send_message_stream(req: ChatRequest):
    async def generate():
        async for chunk in chat_stream(req.user_id, req.message):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")
