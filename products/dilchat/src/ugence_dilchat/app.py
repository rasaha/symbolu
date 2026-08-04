"""FastAPI application factory.

Wires configuration, logging, the database engine, the token service, the
astrology provider, middleware, error handlers, and the versioned router. Route
handlers contain no business logic. No Guna Milan / AI / chat routes are mounted.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import __version__
from .api.router import api_router
from .astrology.registry import build_provider
from .config import Settings, get_settings
from .correlation import CorrelationIdMiddleware
from .db import dispose_engine, init_engine, is_initialized
from .errors import DilChatError, dilchat_error_handler, unhandled_error_handler
from .logging import configure_logging
from .security.tokens import TokenService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.debug)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Idempotent: tests may pre-initialise the engine and own its lifecycle.
        owns_engine = not is_initialized()
        if owns_engine:
            init_engine(settings)
        yield
        if owns_engine:
            await dispose_engine()

    app = FastAPI(
        title="DilChat Backend (Phase A/B)",
        version=__version__,
        description=(
            "DilChat backend foundation (Ugence Labs): identity, birth profiles, "
            "deterministic natal-Moon derivation, three-scope authorization, and "
            "couple/consent/audit primitives. No user-facing Guna Milan, AI, daily "
            "transits, chat, or agreements are exposed in this phase."
        ),
        lifespan=lifespan,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
    )

    # Application-scoped singletons.
    app.state.settings = settings
    app.state.token_service = TokenService(settings)
    app.state.astrology_provider = build_provider(settings)

    app.add_middleware(CorrelationIdMiddleware)
    # Starlette types handlers against Exception; our handlers narrow the type.
    app.add_exception_handler(DilChatError, dilchat_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app
