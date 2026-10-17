"""FastAPI application factory for regista-core."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from regista_core import __version__
from regista_core.api import system
from regista_core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app; pass ``settings`` to bypass the environment (tests do)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "regista-core started",
            extra={"version": __version__, **settings.runtime_modes().model_dump()},
        )
        yield
        logger.info("regista-core stopped")

    app = FastAPI(title="REGISTA core", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(system.router)
    return app
