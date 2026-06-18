"""FastAPI application entrypoint.

Loads the priority model once at startup (fail loud — the app refuses to boot
if the model can't load) and exposes the analyze + health endpoints. All
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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from priormail.api import analyze, health
from priormail.core.config import get_settings
from priormail.core.errors import AppError, ValidationError
from priormail.core.logging import configure_logging, get_logger
from priormail.models.schemas.envelope import failure
from priormail.services.classifier import load_priority_classifier

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)

# Rate limiter — keyed by client IP (CLAUDE.md §9, API_CONTRACT.md §4).
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load models and initialise pipeline on startup."""
    settings = get_settings()
    configure_logging(
        log_level=settings.log_level,
        json_logs=settings.environment != "development",
    )

    # ML model — raises ModelUnavailableError on failure → app refuses to start.
    app.state.priority_classifier = load_priority_classifier(settings)

    # Load public phishing model (no token needed)
    from priormail.services.phishing import load_phishing_classifier
    app.state.phishing_model, app.state.phishing_tokenizer = load_phishing_classifier(settings)
    logger.info("phishing_model_loaded")

    from priormail.agents.graph import build_graph
    from priormail.services.llm_client import build_llm_client

    app.state.pipeline = build_graph(
        priority_classifier=app.state.priority_classifier,
        phishing_model=app.state.phishing_model,
        phishing_tokenizer=app.state.phishing_tokenizer,
        phishing_version=app.state.priority_classifier.version,
        llm_client=build_llm_client(),
    )

    logger.info("app_started", environment=settings.environment)
    yield

    logger.info("app_stopping")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI app."""
    settings = get_settings()
    app = FastAPI(title="PriorMail Backend", version="0.1.0", lifespan=lifespan)

    # Attach the rate limiter to app.state so slowapi can find it.
    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(analyze.router)
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

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        retry_after = getattr(exc, "retry_after", 60)
        body = failure("rate_limit.ip", "Rate limit exceeded. Try again later.")
        return JSONResponse(
            status_code=429,
            content=jsonable_encoder(body),
            headers={"Retry-After": str(retry_after)},
        )


app = create_app()
