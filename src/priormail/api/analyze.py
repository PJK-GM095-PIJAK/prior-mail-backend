"""POST /api/v1/emails/analyze — upload a .eml and get the full analysis."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from priormail.core.errors import FileTooLargeError
from priormail.core.logging import get_logger
from priormail.models.schemas.analysis import AnalysisResult, ExtractedTask
from priormail.models.schemas.envelope import Envelope, success

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/emails", tags=["analyze"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
PIPELINE_TIMEOUT_SECONDS = 30  # SECURITY.md §7


# Shared limiter instance — must match the one attached to app.state in main.py.
limiter = Limiter(key_func=get_remote_address)


@router.post("/analyze", response_model=Envelope[AnalysisResult])
@limiter.limit("30/hour")
async def analyze_email(
    request: Request,
    file: UploadFile,
) -> Envelope[AnalysisResult]:
    """Parse a .eml file and run the full LangGraph pipeline."""

    # 1. Size check — reject before reading the whole file.
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise FileTooLargeError("File exceeds the 5 MB limit.")

    # 2. Get the compiled pipeline from app state.
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        from priormail.core.errors import ModelUnavailableError
        raise ModelUnavailableError("Pipeline is not initialised.")

    # 3. Run the pipeline with a 30s timeout (SECURITY.md §7).
    from priormail.agents.state import PipelineState
    initial_state = PipelineState(raw_eml=contents)
    try:
        raw_result = await asyncio.wait_for(
            asyncio.to_thread(pipeline.invoke, initial_state),
            timeout=PIPELINE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("pipeline_timeout", timeout=PIPELINE_TIMEOUT_SECONDS)
        from priormail.core.errors import AppError
        raise AppError(
            "Processing timed out.",
            code="service.timeout",
            http_status=504,
        )

    # LangGraph returns a dict; convert back to PipelineState for typed access.
    result_state = PipelineState(**raw_result) if isinstance(raw_result, dict) else raw_result

    # 4. Build the response.
    result = AnalysisResult(
        subject=result_state.subject,
        sender_email=result_state.sender_email,
        sender_name=result_state.sender_name,
        received_at=result_state.received_at,
        snippet=result_state.snippet,
        body_text=result_state.body_text,
        is_phishing=result_state.is_phishing,
        phishing_score=result_state.phishing_score,
        priority=result_state.priority,
        priority_confidence=result_state.priority_confidence,
        summary=result_state.summary,
        tasks=[ExtractedTask(**t) for t in result_state.tasks],
        processed_at=datetime.now(UTC),
        model_versions={
            "phishing": result_state.phishing_model_version,
            "priority": result_state.priority_model_version,
        },
    )
    return success(result)
