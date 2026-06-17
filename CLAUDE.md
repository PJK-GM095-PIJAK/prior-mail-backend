# prior-mail-backend — AI Coding Guide

> This file is the primary context for any LLM coding assistant (Claude Code, Cursor, Copilot, etc.) working on **this backend repo**. Read it before writing code.

---

## 1. Repo Role

This is the **backend** repo of PriorMail. It owns:

- `.eml` file parsing (Python stdlib `email` module)
- FastAPI REST API consumed by `prior-mail-frontend`
- LangGraph pipeline (`detect_phishing → classify_priority → summarize → extract_tasks`)
- Hosting: **Render** (Web Service only — no background worker)

The backend is **fully stateless**: it receives an `.eml`, processes it in memory, returns the result. No database, no user sessions.

### Sibling repos

| Repo | Role |
|---|---|
| [`prior-mail-frontend`](https://github.com/PJK-GM095-PIJAK/prior-mail-frontend) | Next.js dashboard; consumes this API |
| [`prior-mail-model`](https://github.com/PJK-GM095-PIJAK/prior-mail-model) | ML training; produces checkpoints this repo loads at inference |
| [`prior-mail-docs`](https://github.com/PJK-GM095-PIJAK/prior-mail-docs) | Shared specs (API, data models, architecture) — mounted as submodule at `./docs/` |

Team ID: **PJK-GM095**

---

## 2. Shared Specs (Submodule)

Cross-repo specs live in `./docs/` (git submodule pointing to `prior-mail-docs`).

**If `./docs/` is empty, run:**
```bash
git submodule update --init --recursive
```

**Files you must check before coding:**
- `./docs/API_CONTRACT.md` — before adding/modifying any endpoint
- `./docs/DATA_MODELS.md` — before creating or modifying any Pydantic model
- `./docs/ARCHITECTURE.md` — for cross-repo flow understanding
- `./docs/SECURITY.md` — before touching file upload handling, secrets, or logging

**Updating the submodule:**
```bash
git submodule update --remote docs
git add docs && git commit -m "chore: bump docs submodule"
```

**Contract changes:** open a PR in `prior-mail-docs` first, get sign-off, then bump the submodule pointer here.

---

## 3. Quick Start for LLM Assistants

Before writing code:

1. Read this entire file.
2. Read the relevant file(s) in `./docs/`.
3. Run tests after changes: `make test`.

When uncertain — ask, don't assume:

- Ambiguous requirement → ask the user.
- Library not in the locked stack → propose first, do not auto-install.
- Cost-sensitive operation (hosted LLM call, model download) → confirm first.

---

## 4. Tech Stack (LOCKED)

### Runtime
- **Python:** 3.11 — dependency manager: `uv`

### Web & API
- **FastAPI** ≥ 0.115 — async by default
- **Pydantic v2** — use `BaseModel`, never v1 syntax
- **Uvicorn** — ASGI server
- **HTTPX** — for all outbound HTTP (never `requests`)
- **python-multipart** — for `.eml` file upload parsing

### Storage
- **Supabase Storage** — model checkpoint download at startup only. No Postgres, no Auth, no Vault.

### AI Orchestration
- **LangGraph** ≥ 0.2 — primary multi-agent orchestration
- **LangChain** — only for model wrappers if strictly needed; prefer raw HTTP + LangGraph nodes
- **Transformers (Hugging Face)** — for loading DistilBERT checkpoints (trained in `prior-mail-model`)
- **PyTorch 2.x**

### Observability & Logging
- **structlog** — JSON output in prod

### Dev Tooling
- **Lint + format:** `ruff` (replaces black + isort + flake8)
- **Type check:** `mypy --strict` — CI gate
- **Tests:** `pytest` + `pytest-asyncio`
- **Pre-commit:** `pre-commit` with hooks for ruff and mypy

> **Do not** add a new dependency without proposing it first. **Do not** swap any of the above.

---

## 5. Repository Structure

```
prior-mail-backend/
├── CLAUDE.md                  ← you are here
├── README.md
├── Makefile
├── pyproject.toml
├── docs/                      ← submodule → prior-mail-docs
├── src/priormail/
│   ├── api/                   ← FastAPI routers (one file per resource)
│   │   ├── analyze.py         ← POST /api/v1/emails/analyze
│   │   └── health.py
│   ├── agents/                ← LangGraph nodes + graph definitions
│   │   ├── state.py           ← Pydantic pipeline state model
│   │   ├── parse_eml.py       ← parse raw .eml bytes → structured fields
│   │   ├── preprocess.py      ← strip HTML, normalize text
│   │   ├── phishing.py        ← phishing detection node
│   │   ├── classify.py        ← priority classification node
│   │   ├── summarize.py       ← LLM summarization node
│   │   ├── extract_tasks.py   ← LLM task extraction node
│   │   └── graph.py           ← assembles the LangGraph
│   ├── models/                ← Pydantic schemas (request/response only, no ORM)
│   ├── services/              ← integration layer (model_loader, llm_client)
│   ├── core/                  ← config, deps, errors, logging
└── tests/
    ├── unit/
    ├── integration/
    └── conftest.py
```

---

## 6. API Endpoints (overview)

> **Full spec:** `./docs/API_CONTRACT.md`. All JSON responses use envelope `{ data, error, meta }`. Error codes are machine-readable strings (see `core/errors.py`), not HTTP status alone.

```
POST   /api/v1/emails/analyze   ← upload .eml, returns full classification result
GET    /api/v1/health            ← liveness check
GET    /api/v1/health/models     ← model load status + versions
```

**No authentication required.** The backend holds no user data.

---

## 7. ML Model Integration

Models are **trained in `prior-mail-model`** and consumed here at inference time.

### Contract with `prior-mail-model`
- Trained checkpoints are on HuggingFace Hub (current) or Supabase Storage (intended)
- This repo references them via env vars:
  - `PRIORITY_MODEL_URI`
  - `PHISHING_MODEL_URI`
- Checkpoint format: see `./docs/ML_PIPELINE.md`

### Loading strategy
- Models loaded **once at app startup** (FastAPI lifespan event), never per-request.
- Pinned to specific versions in env — do **not** auto-pull "latest".
- Failed model load → app refuses to start (fail loud).

### Inference rules
- All inference runs in-process (no separate model server for MVP).
- Latency budget: p95 < 500 ms per email on Render Standard instance.
- CPU-bound inference must be offloaded with `asyncio.to_thread` — never block the event loop directly in a route handler.

---

## 8. Coding Conventions

- **Async by default** for I/O (handlers, HTTP calls).
- **Type hints required**; `mypy --strict` must pass.
- **Dependency injection** via FastAPI `Depends(...)` — no module-level globals for state.
- **Errors:** raise typed exceptions from `core/errors.py`, never bare `Exception`.
- **Settings:** `pydantic-settings`, read from env, validate on startup. App must refuse to boot if config is invalid.
- **Logging:** structured JSON via `structlog`. Never log full email bodies (snippet only, max 100 chars).
- **File naming:** `snake_case.py`. Constants: `UPPER_SNAKE_CASE`.
- **Tests:** `test_<module>.py`, one test class per scenario.

### Git
- Branches: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- PRs: must pass CI (lint + type + test) before merge
- No direct pushes to `main`

### LangGraph
- Each node is a pure function: `(State) -> State` (or `(State) -> Partial[State]`)
- No side effects anywhere — no DB writes, no fire-and-forget calls inside nodes
- State schema is a Pydantic model in `agents/state.py`
- Pipeline is sequential: `parse_eml → preprocess → detect_phishing → (short-circuit if phishing) → classify_priority → summarize → extract_tasks`
- Tests must cover each node independently before testing the full graph

---

## 9. Security & Privacy (CRITICAL)

> Full policy: `./docs/SECURITY.md`. Backend-specific musts below.

### Must
- Enforce 5 MB file size limit on upload — reject before parsing
- Validate that the uploaded file is parseable as `message/rfc822`; do not trust `Content-Type` header
- Never log full email body (snippet only, max 100 chars)
- Never send email content to any third party except the chosen LLM provider
- Never include email content in error messages or stack traces
- Rate-limit by IP on all endpoints (use `slowapi` or middleware)
- All secrets from env vars; loaded via `pydantic-settings`

### Never
- Do **not** write email content to disk, a database, or a cache
- Do **not** commit `.env` or model checkpoints
- Do **not** use `requests` (sync) — always `httpx.AsyncClient`

---

## 10. Do NOT (Anti-patterns)

- Do **not** add a dependency without proposing it
- Do **not** swap items in "Tech Stack (LOCKED)"
- Do **not** add any database (SQLAlchemy, Alembic, Supabase Postgres) — the backend is intentionally stateless
- Do **not** add authentication or session management — no user accounts
- Do **not** use Pydantic v1 syntax (`class Config:`, `@validator`)
- Do **not** put model inference in route handlers without `asyncio.to_thread` offload
- Do **not** hardcode URLs, keys, or model URIs — always config
- Do **not** silently swallow exceptions

---

## 11. Definition of Done

A feature is done when **all** apply:

- [ ] `ruff check`, `mypy --strict`, `pytest` all pass
- [ ] New endpoints documented in `./docs/API_CONTRACT.md` (via PR to `prior-mail-docs`)
- [ ] New response fields documented in `./docs/DATA_MODELS.md` (same)
- [ ] Unit tests ≥ 70% coverage on new code
- [ ] Integration test for happy path
- [ ] Errors handled via typed exceptions
- [ ] No `print()`, no committed secrets, no debug code
- [ ] PR description explains *why*, not just *what*

---

## 12. Common Commands

```bash
make install                  # uv pip install -e ".[dev]"
make dev                      # uvicorn with reload
make test                     # pytest + coverage
make lint                     # ruff check + mypy --strict
make format                   # ruff format

# Submodule
git submodule update --init --recursive    # after fresh clone
git submodule update --remote docs         # pull latest shared specs
```

---

## 13. Open Decisions

LLMs: do **not** assume an answer — ask.

- [ ] Summarizer + task extractor: hosted LLM (Anthropic / OpenAI) vs local (Llama / Mistral)?
- [ ] `.eml` file size limit: 5 MB confirmed or adjust?

---

## 14. Owners

- **Syafiq** — FastAPI scaffolding, `.eml` parsing, infra/deployment
- **Insan** — Model loading & inference integration
- **Faiz** — Phishing detector integration, security review
- **Ridjal** — LangGraph nodes (shared with Faiz)

---

*Last updated: 2026-06-17*
