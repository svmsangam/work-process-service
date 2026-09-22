from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import work_items

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables on startup (bypassed in pytest via dependency override)
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-Assisted Work Intake System API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(work_items.router)

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "provider": settings.AI_PROVIDER}