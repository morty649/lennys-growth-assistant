from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent_client import AgentServiceError
from app.client_auth import validate_auth_configuration
from app.database import initialize_database
from app.dependencies import settings
from app.indexing import maybe_start_ingestion
from app.routers import artifacts, chat, client, health, ingestion, sessions, tools

logger = logging.getLogger("lenny.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_auth_configuration()
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
        allow_origins=list(dict.fromkeys([
            *settings.web_origins,
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ])),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AgentServiceError)
    async def agent_service_error_handler(request, exc: AgentServiceError):
        logger.warning(
            json.dumps(
                {
                    "event": "agent_service_error",
                    "path": request.url.path,
                    "code": exc.code,
                    "status": exc.status_code,
                }
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "detail": exc.detail},
        )

    @application.middleware("http")
    async def structured_request_log(request, call_next):
        started = perf_counter()
        response = await call_next(request)
        if request.url.path != "/health/live":
            logger.info(json.dumps({
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }))
        return response

    for router in (
        health.router,
        client.router,
        sessions.router,
        chat.router,
        artifacts.router,
        ingestion.router,
        tools.router,
    ):
        application.include_router(router)
    return application


app = create_app()
