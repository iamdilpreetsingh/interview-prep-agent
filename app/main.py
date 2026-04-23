from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes import chat, dashboard, goals, profile

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Mikasa - Interview Prep Agent",
    description="AI-powered interview coach for SDE roles at top tech companies",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(chat.router)
app.include_router(profile.router)
app.include_router(goals.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug/check-api")
async def check_api():
    """Test that the Anthropic API key works."""
    from app.config import settings
    key = settings.anthropic_api_key
    model = settings.claude_model
    masked = key[:10] + "..." + key[-4:] if len(key) > 14 else "TOO_SHORT"
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=key)
        resp = await client.messages.create(model=model, max_tokens=10, messages=[{"role": "user", "content": "hi"}])
        return {"status": "ok", "key": masked, "model": model, "response": resp.content[0].text}
    except Exception as e:
        return {"status": "error", "key": masked, "model": model, "error": str(e)}


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
