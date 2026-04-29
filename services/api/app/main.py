from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.chroma_client import ensure_collection
from app.api import ai as ai_router
from app.api import auth as auth_router
from app.api import documents as documents_router
from app.api import health as health_router
from app.api import ingest as ingest_router
from app.api import jobs as jobs_router
from app.api import search as search_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import CSRFMiddleware, RequestContextMiddleware

log = logging.getLogger("api.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("INFO" if get_settings().is_production else "DEBUG")
    log.info("api.startup", extra={"env": get_settings().APP_ENV})
    await ensure_collection()
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="KnowledgeOps AI — API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(RequestContextMiddleware)

    install_error_handlers(app)

    app.include_router(health_router.router)
    app.include_router(auth_router.router)
    app.include_router(documents_router.router)
    app.include_router(ingest_router.router)
    app.include_router(jobs_router.router)
    app.include_router(ai_router.router)
    app.include_router(search_router.router)

    return app


app = create_app()
