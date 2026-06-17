# Backend Refactor Instructions

> **For Syafiq.** The project architecture changed on 2026-06-17. We dropped Gmail API + Supabase Postgres and switched to a stateless `.eml` upload model. This doc tells you exactly what to delete, what to keep, and what to build. Read `CLAUDE.md` and `docs/ARCHITECTURE.md` first if you haven't.

---

## Overview of the change

**Before:** Frontend connects Gmail via OAuth → backend syncs inbox → stores emails in Postgres → returns them.

**After:** User drops a `.eml` file on the frontend → frontend sends it to `POST /api/v1/emails/analyze` → backend parses, runs the LangGraph pipeline, returns the result → frontend stores in `localStorage`. Backend is now 100% stateless.

---

## Step 1 — Delete files that are no longer needed

Delete these files entirely. They are all Gmail/DB-specific and have no role in the new architecture.

```
src/priormail/api/auth.py          ← Gmail OAuth callback
src/priormail/api/sync_router.py   ← Gmail sync trigger
src/priormail/api/emails.py        ← email list/detail from DB
src/priormail/services/gmail_client.py
src/priormail/services/sync.py
src/priormail/models/orm/          ← entire folder (SQLAlchemy ORM models)
src/priormail/workers/             ← entire folder (background sync worker)
alembic/                           ← entire folder (DB migrations)
alembic.ini
```

Also remove these packages from `pyproject.toml` / `requirements.txt`:
```
sqlalchemy
asyncpg
alembic
google-api-python-client
google-auth
google-auth-httplib2
python-jose          # JWT validation, no longer needed
```

---

## Step 2 — Clean up files you're keeping

### `src/priormail/core/config.py`

Remove these settings fields (they're all DB/OAuth related):

```python
# DELETE these fields from Settings:
database_url
database_ssl
database_pool_size
supabase_url
supabase_jwt_secret
google_client_id
google_client_secret
google_redirect_uri
```

Keep:
- `priority_model_uri` + validators + properties
- `phishing_model_uri` + validators + properties
- `cors_origins`
- `environment`
- `log_level`

Add these new fields for the LLM:
```python
groq_api_key: str = Field(default="", description="Groq API key for summarization + task extraction.")
llm_model: str = Field(
    default="llama-3.1-8b-instant",
    description=(
        "Groq model ID. Use 'llama-3.1-8b-instant' for dev/testing (14.4K RPD free tier). "
        "Switch to 'llama-3.3-70b-versatile' for demo day (better quality, 1K RPD is fine for a demo)."
    ),
)
```

---

### `src/priormail/core/deps.py`

Remove:
- `get_db` — no database
- `get_current_user` — no user accounts
- `get_current_user_id` — no JWT auth
- `_bearer_scheme` — no auth header

Keep:
- `get_priority_classifier`
- `get_phishing_classifier`

The file after cleanup should be about 20 lines.

---

### `src/priormail/core/errors.py`

Remove:
- `AuthenticationError`
- `DatabaseError`
- `GmailApiError`

Keep:
- `AppError` (base)
- `ModelUnavailableError`
- `ValidationError`
- `NotFoundError`

Add:
```python
class EmlParseError(AppError):
    """Raised when the uploaded .eml file cannot be parsed."""
    http_status = 400
    code = "email.parse_failed"

class FileTooLargeError(AppError):
    """Raised when the uploaded file exceeds the size limit."""
    http_status = 413
    code = "email.file_too_large"
```

---

### `src/priormail/main.py`

Remove from `lifespan`:
- `create_db_engine` call and everything related to `app.state.db_engine` / `app.state.db_session_factory`
- `engine.dispose()` on shutdown

Remove from `create_app`:
- `app.include_router(auth.router)`
- `app.include_router(sync_router.router)`
- `app.include_router(emails.router)`

Add:
```python
from priormail.api import analyze   # new router (Step 3)
# ...
app.include_router(analyze.router)
```

Remove from imports:
```python
from priormail.models.orm.db import create_db_engine   # delete this
```

---

## Step 3 — Build the new pieces

### 3.1 New response schema: `src/priormail/models/schemas/analysis.py`

Create this file. It defines what the API returns.

```python
from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, Field
from priormail.models.schemas.priority import Priority  # reuse existing enum

class ExtractedTask(BaseModel):
    description: str
    due_date: date | None = None

class AnalysisResult(BaseModel):
    subject: str
    sender_email: str
    sender_name: str | None = None
    received_at: datetime | None = None
    snippet: str                              # first 200 chars of body
    body_text: str
    is_phishing: bool
    phishing_score: float = Field(ge=0, le=1)
    priority: Priority | None = None          # None when is_phishing=True
    priority_confidence: float = Field(default=0.0, ge=0, le=1)
    summary: str | None = None
    tasks: list[ExtractedTask] = []
    processed_at: datetime
    model_versions: dict[str, str] = {}
```

---

### 3.2 LangGraph pipeline state: `src/priormail/agents/state.py`

```python
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field

class PipelineState(BaseModel):
    # --- Input (set by parse_eml node) ---
    raw_eml: bytes = b""
    subject: str = ""
    sender_email: str = ""
    sender_name: str | None = None
    received_at: datetime | None = None
    body_text: str = ""
    snippet: str = ""

    # --- Phishing node output ---
    is_phishing: bool = False
    phishing_score: float = 0.0
    phishing_model_version: str = ""

    # --- Priority node output (skipped if is_phishing=True) ---
    priority: str | None = None
    priority_confidence: float = 0.0
    priority_model_version: str = ""

    # --- LLM node outputs ---
    summary: str | None = None
    tasks: list[dict] = Field(default_factory=list)  # {description, due_date}

    # --- Meta ---
    processed_at: datetime | None = None
    error: str | None = None
```

---

### 3.3 LangGraph nodes

Create one file per node under `src/priormail/agents/`.

#### `parse_eml.py`

```python
import email as email_lib
from email import policy
from priormail.agents.state import PipelineState
from priormail.core.errors import EmlParseError

def parse_eml(state: PipelineState) -> dict:
    """Parse raw .eml bytes and extract structured fields."""
    try:
        msg = email_lib.message_from_bytes(state.raw_eml, policy=policy.default)
    except Exception as exc:
        raise EmlParseError(f"Cannot parse .eml: {exc}") from exc

    subject = msg.get("Subject", "") or ""
    sender = msg.get("From", "") or ""
    date_str = msg.get("Date")

    # Parse sender into email + name
    from email.utils import parseaddr, parsedate_to_datetime
    sender_name, sender_email = parseaddr(sender)

    # Parse date
    received_at = None
    if date_str:
        try:
            received_at = parsedate_to_datetime(date_str)
        except Exception:
            pass

    # Extract plain-text body
    body_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body_text = part.get_content() or ""
                break
    else:
        if msg.get_content_type() == "text/plain":
            body_text = msg.get_content() or ""

    snippet = body_text[:200]

    return {
        "subject": subject,
        "sender_email": sender_email,
        "sender_name": sender_name or None,
        "received_at": received_at,
        "body_text": body_text,
        "snippet": snippet,
    }
```

#### `preprocess.py`

```python
from priormail.agents.state import PipelineState
from priormail.services.preprocess import clean_text

def preprocess(state: PipelineState) -> dict:
    """Normalize subject and body text for model input."""
    return {
        "body_text": clean_text(state.body_text),
        "subject": clean_text(state.subject),
        "snippet": state.body_text[:200],  # snippet from raw, before cleaning
    }
```

#### `phishing.py`

```python
import asyncio
from priormail.agents.state import PipelineState
from priormail.services.phishing_inference import predict_phishing

def detect_phishing(state: PipelineState, model, tokenizer, version: str) -> dict:
    """Run phishing detection. Returns early flag if phishing."""
    from priormail.services.preprocess import build_priority_input
    text = build_priority_input(state.subject, state.body_text)
    is_phishing, score = predict_phishing(model, tokenizer, text)
    return {
        "is_phishing": is_phishing,
        "phishing_score": score,
        "phishing_model_version": version,
    }
```

#### `classify.py`

```python
from priormail.agents.state import PipelineState

def classify_priority(state: PipelineState, classifier) -> dict:
    """Run priority classification. Only called when is_phishing=False."""
    prediction = classifier.classify(state.subject, state.body_text)
    return {
        "priority": prediction.label,
        "priority_confidence": prediction.confidence,
        "priority_model_version": classifier.version,
    }
```

#### `summarize.py` and `extract_tasks.py`

**LLM provider decided: Groq.** Install the SDK:
```bash
uv add groq
```

Build a shared client in `services/llm_client.py` and pass it into the nodes:

```python
# services/llm_client.py
from groq import Groq
from priormail.core.config import get_settings

def build_llm_client() -> Groq:
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key)
```

Then the nodes:

```python
# agents/summarize.py
from groq import Groq
from priormail.agents.state import PipelineState

SUMMARIZE_PROMPT = """\
Summarize the following email in 2-3 sentences. Be concise and focus on the key point and any required action.

Subject: {subject}
From: {sender}

{body}

Summary:"""

def summarize(state: PipelineState, llm_client: Groq) -> dict:
    """Call Groq to generate a short email summary."""
    from priormail.core.config import get_settings
    settings = get_settings()

    prompt = SUMMARIZE_PROMPT.format(
        subject=state.subject,
        sender=state.sender_email,
        body=state.body_text[:3000],  # cap to stay within TPM budget
    )
    response = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
    )
    summary = response.choices[0].message.content.strip()
    return {"summary": summary}
```

```python
# agents/extract_tasks.py
import json
from groq import Groq
from priormail.agents.state import PipelineState

TASK_PROMPT = """\
Extract any actionable tasks or deadlines from the email below.
Return a JSON array. Each item must have "description" (string) and "due_date" (YYYY-MM-DD or null).
If there are no tasks, return an empty array [].
Return ONLY the JSON array, no explanation.

Subject: {subject}
From: {sender}

{body}"""

def extract_tasks(state: PipelineState, llm_client: Groq) -> dict:
    """Call Groq to extract tasks as a JSON array."""
    from priormail.core.config import get_settings
    settings = get_settings()

    prompt = TASK_PROMPT.format(
        subject=state.subject,
        sender=state.sender_email,
        body=state.body_text[:3000],
    )
    response = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.1,  # low temp for structured output
    )
    raw = response.choices[0].message.content.strip()

    # Parse JSON — one retry with a format reminder if it fails.
    try:
        tasks = json.loads(raw)
        if not isinstance(tasks, list):
            tasks = []
    except json.JSONDecodeError:
        tasks = []

    return {"tasks": tasks}
```

**Model to use:**
- Development/testing: `llama-3.1-8b-instant` (default) — 14.4K RPD free tier, fast
- Demo day: set `LLM_MODEL=llama-3.3-70b-versatile` in Render env vars — better quality, 1K RPD is fine for a demo

No code change needed to switch models, just update the env var.

---

#### `graph.py` — assembles the LangGraph

```python
from __future__ import annotations
from langgraph.graph import StateGraph, END
from priormail.agents.state import PipelineState
from priormail.agents import parse_eml, preprocess, phishing, classify, summarize, extract_tasks

def build_graph(priority_classifier, phishing_model, phishing_tokenizer, phishing_version, llm_client):
    """Build and compile the LangGraph pipeline."""

    def _parse(state):
        return parse_eml.parse_eml(state)

    def _preprocess(state):
        return preprocess.preprocess(state)

    def _phishing(state):
        return phishing.detect_phishing(
            state, phishing_model, phishing_tokenizer, phishing_version
        )

    def _classify(state):
        return classify.classify_priority(state, priority_classifier)

    def _summarize(state):
        return summarize.summarize(state, llm_client)

    def _extract_tasks(state):
        return extract_tasks.extract_tasks(state, llm_client)

    def _route_after_phishing(state: PipelineState) -> str:
        """Short-circuit to END if phishing; otherwise continue to classify."""
        return "end" if state.is_phishing else "classify"

    graph = StateGraph(PipelineState)
    graph.add_node("parse_eml", _parse)
    graph.add_node("preprocess", _preprocess)
    graph.add_node("detect_phishing", _phishing)
    graph.add_node("classify_priority", _classify)
    graph.add_node("summarize", _summarize)
    graph.add_node("extract_tasks", _extract_tasks)

    graph.set_entry_point("parse_eml")
    graph.add_edge("parse_eml", "preprocess")
    graph.add_edge("preprocess", "detect_phishing")
    graph.add_conditional_edges(
        "detect_phishing",
        _route_after_phishing,
        {"end": END, "classify": "classify_priority"},
    )
    graph.add_edge("classify_priority", "summarize")
    graph.add_edge("summarize", "extract_tasks")
    graph.add_edge("extract_tasks", END)

    return graph.compile()
```

Store the compiled graph on `app.state.pipeline` in `main.py` lifespan.

---

### 3.4 New API endpoint: `src/priormail/api/analyze.py`

```python
"""POST /api/v1/emails/analyze — upload a .eml and get the full analysis."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, UploadFile

from priormail.core.errors import EmlParseError, FileTooLargeError
from priormail.models.schemas.analysis import AnalysisResult, ExtractedTask
from priormail.models.schemas.envelope import Envelope, success

router = APIRouter(prefix="/api/v1/emails", tags=["analyze"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/analyze", response_model=Envelope[AnalysisResult])
async def analyze_email(
    file: UploadFile,
    request: Request,
) -> Envelope[AnalysisResult]:
    """Parse a .eml file and run the full LangGraph pipeline."""
    import asyncio

    # 1. Size check — reject before reading the whole file.
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise FileTooLargeError("File exceeds the 5 MB limit.")

    # 2. Get the compiled pipeline from app state.
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        from priormail.core.errors import ModelUnavailableError
        raise ModelUnavailableError("Pipeline is not initialised.")

    # 3. Run the pipeline (CPU-bound parts offloaded inside nodes).
    from priormail.agents.state import PipelineState
    initial_state = PipelineState(raw_eml=contents)
    result_state: PipelineState = await asyncio.to_thread(pipeline.invoke, initial_state)

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
        processed_at=datetime.now(timezone.utc),
        model_versions={
            "phishing": result_state.phishing_model_version,
            "priority": result_state.priority_model_version,
        },
    )
    return success(result)
```

---

## Step 4 — Wire the pipeline in `main.py`

In the `lifespan` function, after loading both models, build and store the graph:

```python
from priormail.agents.graph import build_graph

# after loading models...
app.state.pipeline = build_graph(
    priority_classifier=app.state.priority_classifier,
    phishing_model=app.state.phishing_model,
    phishing_tokenizer=app.state.phishing_tokenizer,
    phishing_version=app.state.priority_classifier.version,  # or separate
    llm_client=build_llm_client(),  # Groq — see services/llm_client.py
)
```

---

## Step 5 — Update the health endpoint

`GET /api/v1/health/models` should return the loaded model versions. Update `api/health.py`:

```python
@router.get("/health/models")
async def health_models(request: Request):
    classifier = getattr(request.app.state, "priority_classifier", None)
    phishing = getattr(request.app.state, "phishing_model", None)
    return success({
        "priority_classifier": {
            "status": "loaded" if classifier else "unavailable",
            "version": classifier.version if classifier else None,
        },
        "phishing_detector": {
            "status": "loaded" if phishing else "unavailable",
        },
    })
```

---

## Step 6 — Verify

After making the changes, run:

```bash
make lint         # ruff check + mypy --strict
make test         # pytest
make dev          # start the server

# Quick smoke test:
curl -X POST http://localhost:8000/api/v1/emails/analyze \
  -F "file=@/path/to/test.eml"
```

The response should be an `AnalysisResult` JSON wrapped in `{ data, error, meta }`.

---

## What does NOT change

- `services/classifier.py` — keep as-is
- `services/phishing_inference.py` — keep as-is
- `services/phishing.py` — keep as-is
- `services/preprocess.py` — keep as-is
- `core/config.py` model URI settings — keep as-is
- `core/errors.py` base class + `ModelUnavailableError` — keep
- `core/logging.py` — keep as-is
- `models/schemas/envelope.py` — keep as-is
- The existing standalone `/api/v1/classify/priority` and `/api/v1/classify/phishing` endpoints — you can keep them temporarily as a fallback, or delete them once the full pipeline is working

---

## LLM decision (resolved)

**Provider: Groq** (free tier, no credit card needed for capstone).

| Use case | Model | Why |
|---|---|---|
| Dev & testing | `llama-3.1-8b-instant` | 14.4K RPD — test freely without hitting the cap |
| Demo day | `llama-3.3-70b-versatile` | Better summarization quality; 1K RPD is enough for a demo |

Switch by changing `LLM_MODEL` in the Render environment variables — no code change needed.

---

*Written: 2026-06-17*
