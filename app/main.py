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


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
