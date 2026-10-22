"""
FastAPI application entry point.

Endpoints:
  GET  /api/health     — liveness + model/storage status
  POST /api/match      — main endpoint: PDF → live ranked jobs
  POST /api/embed      — debug: see the embedding vector for any text
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from api.routes import router
from api.auth_routes import router as auth_router
from services.embedding_service import embedder
from services.job_store import job_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_store.initialize()
    embedder.load()
    yield


app = FastAPI(
    title="Semantic Job Match Engine",
    description="Upload a resume PDF, get ranked job matches with skill gap analysis.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
