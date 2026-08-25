from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import initialize_database
from app.dependencies import settings
from app.indexing import maybe_start_ingestion
from app.routers import artifacts, chat, health, ingestion, sessions, tools


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(initialize_database)
    maybe_start_ingestion()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Lenny's Growth Assistant API",
        version="0.1.0",
        description="Local-first grounded conversational API over Lenny's Podcast transcripts.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin, "http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (
        health.router,
        sessions.router,
        chat.router,
        artifacts.router,
        ingestion.router,
        tools.router,
    ):
        application.include_router(router)
    return application


app = create_app()
