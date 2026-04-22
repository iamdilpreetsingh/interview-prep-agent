from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routes import chat, goals, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="CrackCode - Interview Prep Agent",
    description="AI-powered interview coach for SDE roles at top tech companies",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(chat.router)
app.include_router(profile.router)
app.include_router(goals.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
