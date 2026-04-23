import traceback

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent import chat, chat_stream
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(req: ChatRequest):
    try:
        reply, tools_used = await chat(req.user_id, req.message)
        return ChatResponse(reply=reply, tools_used=tools_used)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"CHAT ERROR: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def send_message_stream(req: ChatRequest):
    async def generate():
        async for chunk in chat_stream(req.user_id, req.message):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")
