"""FastAPI application entrypoint.

Loads the priority model once at startup (fail loud — the app refuses to boot
if the model can't load) and exposes the classify + health endpoints. All
responses use the standard envelope (API_CONTRACT.md §1).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from priormail.api import classify, health
from priormail.core.config import get_settings
from priormail.core.errors import AppError, ValidationError
from priormail.core.logging import configure_logging, get_logger
from priormail.models.envelope import failure
from priormail.services.classifier import load_priority_classifier

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load models on startup; a failure propagates and aborts boot."""
    settings = get_settings()
    configure_logging(
        log_level=settings.log_level,
        json_logs=settings.environment != "development",
    )
    # Raises ModelUnavailableError on failure -> app refuses to start (exits non-zero).
    app.state.priority_classifier = load_priority_classifier(settings)
    logger.info("app_started", environment=settings.environment)
    yield
    logger.info("app_stopping")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI app."""
    settings = get_settings()
    app = FastAPI(title="PriorMail Backend", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(classify.router)
    app.include_router(health.router)

    _register_exception_handlers(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        body = failure(exc.code, exc.message, details=exc.details)
        return JSONResponse(
            status_code=exc.http_status, content=jsonable_encoder(body)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        err = ValidationError("Request validation failed.")
        # Drop 'ctx' — it can carry the raw exception object, which isn't JSON-serializable.
        errors = [{k: v for k, v in e.items() if k != "ctx"} for e in exc.errors()]
        body = failure(err.code, err.message, details={"errors": errors})
        return JSONResponse(
            status_code=err.http_status, content=jsonable_encoder(body)
        )


app = create_app()
