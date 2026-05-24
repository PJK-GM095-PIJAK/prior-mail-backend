# prior-mail-backend — AI Coding Guide

> This file is the primary context for any LLM coding assistant (Claude Code, Cursor, Copilot, etc.) working on **this backend repo**. Read it before writing code.

---

## 1. Repo Role

This is the **backend** repo of PriorMail. It owns:

- Gmail API integration (OAuth, sync, delta updates via `historyId`)
- FastAPI REST API consumed by `prior-mail-frontend`
- LangGraph multi-agent pipeline (`classify → detect_phishing → summarize → extract_tasks`)
- Background sync workers
- Hosting: **Render** (Web Service + Background Worker)

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
- `./docs/DATA_MODELS.md` — before creating any DB query, schema, or Pydantic model
- `./docs/ARCHITECTURE.md` — for cross-repo flow understanding
- `./docs/SECURITY.md` — before touching auth, secrets, or PII

**Updating the submodule:**
```bash
git submodule update --remote docs
git add docs && git commit -m "chore: bump docs submodule"
```

**Schema/contract changes:** open a PR in `prior-mail-docs` first, get sign-off, then bump the submodule pointer here.

---

## 3. Quick Start for LLM Assistants

Before writing code:

1. Read this entire file.
2. Read the relevant file(s) in `./docs/`.
3. Run tests after changes: `make test`.

When uncertain — ask, don't assume:

- Ambiguous requirement → ask the user.
- Library not in the locked stack → propose first, do not auto-install.
- Schema change → write a new migration; propose the matching spec update in `prior-mail-docs`.
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

### Data
- **SQLAlchemy 2.x** async, talking to Supabase Postgres
- **Alembic** — migrations
- **Supabase** — Postgres 15 + Auth + Storage (+ Realtime if needed)

### Auth & External
- **Gmail API** via `google-api-python-client` + `google-auth`
- **Supabase Auth** for user sessions (JWT validation)

### AI Orchestration
- **LangGraph** ≥ 0.2 — primary multi-agent orchestration
- **LangChain** — only for model wrappers if strictly needed; prefer raw HTTP + LangGraph nodes
- **Transformers (Hugging Face)** — for loading IndoBERT checkpoints (trained in `prior-mail-model`)
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
├── alembic.ini
├── docs/                      ← submodule → prior-mail-docs
├── src/priormail/
│   ├── api/                   ← FastAPI routers (one file per resource)
│   ├── agents/                ← LangGraph nodes + graph definitions
│   │   ├── classify.py
│   │   ├── phishing.py
│   │   ├── summarize.py
│   │   ├── extract_tasks.py
│   │   └── graph.py           ← assembles the LangGraph
│   ├── models/                ← SQLAlchemy + Pydantic schemas
│   ├── services/              ← integration layer (gmail_client, model_loader, supabase)
│   ├── core/                  ← config, deps, errors, logging
│   └── workers/               ← background sync jobs
├── alembic/versions/
└── tests/
    ├── unit/
    ├── integration/
    └── conftest.py
```

---

## 6. API Endpoints (overview)

> **Full spec:** `./docs/API_CONTRACT.md`. All JSON responses use envelope `{ data, error, meta }`. Error codes are machine-readable strings (see `core/errors.py`), not HTTP status alone.

```
POST   /api/v1/auth/google/callback     ← OAuth callback
POST   /api/v1/sync                     ← trigger manual sync
GET    /api/v1/emails                   ← ?priority=high&limit=50&cursor=...
GET    /api/v1/emails/{id}              ← single email + full summary
POST   /api/v1/emails/{id}/reclassify   ← re-run AI on demand
GET    /api/v1/tasks                    ← extracted tasks across emails
PATCH  /api/v1/tasks/{id}               ← mark complete / edit
GET    /api/v1/stats                    ← dashboard metrics
DELETE /api/v1/account                  ← GDPR-style data wipe
```

All endpoints (except OAuth callback) require `Authorization: Bearer <supabase_jwt>`.

---

## 7. ML Model Integration

Models are **trained in `prior-mail-model`** and consumed here at inference time.

### Contract with `prior-mail-model`
- Trained checkpoints are uploaded to Supabase Storage under `models/{model_name}/{version}/`
- This repo references them via env vars:
  - `PRIORITY_MODEL_URI` — e.g. `supabase://models/priority/v3/checkpoint.bin`
  - `PHISHING_MODEL_URI` — e.g. `supabase://models/phishing/v2/checkpoint.bin`
- Checkpoint format and required tokenizer config: see `./docs/ML_PIPELINE.md`

### Loading strategy
- Models loaded **once at app startup** (FastAPI lifespan event), never per-request.
- Pinned to specific versions in env — do **not** auto-pull "latest".
- Failed model load → app refuses to start (fail loud).

### Inference rules
- All inference runs in-process (no separate model server for MVP).
- Latency budget: p95 < 500 ms per email on Render Standard instance.
- Batch when possible (process multiple emails in one forward pass during sync).

---

## 8. Coding Conventions

- **Async by default** for I/O (handlers, DB calls, HTTP calls).
- **Type hints required**; `mypy --strict` must pass.
- **Dependency injection** via FastAPI `Depends(...)` — no module-level globals for state.
- **Errors:** raise typed exceptions from `core/errors.py`, never bare `Exception`.
- **Settings:** `pydantic-settings`, read from env, validate on startup. App must refuse to boot if config is invalid.
- **Logging:** structured JSON via `structlog`. Never log full email bodies.
- **File naming:** `snake_case.py`. Constants: `UPPER_SNAKE_CASE`.
- **Tests:** `test_<module>.py`, one test class per scenario.

### Git
- Branches: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- PRs: must pass CI (lint + type + test) before merge
- No direct pushes to `main`

### Migrations
- Every schema change = new Alembic migration file
- **Never** modify an already-applied migration; create a new one
- Filename: `YYYYMMDD_HHMM_<description>.py`
- Always include `downgrade()`, even if it's just `pass` with a comment

### LangGraph
- Each node is a pure function: `(State) -> State` (or `(State) -> Partial[State]`)
- Side effects (DB writes, API calls) only in clearly-named nodes (e.g. `persist_email`)
- State schema is a Pydantic model in `agents/state.py`
- Tests must cover each node independently before testing the full graph

---

## 9. Security & Privacy (CRITICAL)

> Full policy: `./docs/SECURITY.md`. Backend-specific musts below.

### Must
- Encrypt Gmail OAuth refresh tokens at rest (Supabase Vault)
- Delete raw email bodies after 30 days (keep only hash + AI-derived fields)
- Log every email content access in `audit_log` table
- Use **minimum** Gmail scope: `gmail.readonly` for MVP. No `send`, no `modify`
- Validate Supabase JWT on every protected endpoint
- Rate-limit per user on all endpoints (use `slowapi` or middleware)
- All secrets from env vars; loaded via `pydantic-settings`

### Never
- Do **not** log full email bodies (snippet only, max 100 chars in logs)
- Do **not** send email content to any third-party API except the chosen LLM provider (once decided)
- Do **not** include email content in error messages or stack traces
- Do **not** commit `.env`, OAuth client secrets, or model checkpoints
- Do **not** request elevated Gmail scopes in MVP

---

## 10. Do NOT (Anti-patterns)

- Do **not** add a dependency without proposing it
- Do **not** swap items in "Tech Stack (LOCKED)"
- Do **not** use Microsoft Graph / Outlook / EmailEngine — Gmail only for MVP
- Do **not** use `requests` (sync) — always `httpx.AsyncClient`
- Do **not** use Pydantic v1 syntax (`class Config:`, `@validator`)
- Do **not** modify existing migrations
- Do **not** put model inference in route handlers without async offload if it's CPU-bound (use `asyncio.to_thread`)
- Do **not** hardcode URLs, keys, or model URIs — always config
- Do **not** silently swallow exceptions
- Do **not** ship code that calls undocumented Gmail API endpoints

---

## 11. Definition of Done

A feature is done when **all** apply:

- [ ] `ruff check`, `mypy --strict`, `pytest` all pass
- [ ] New endpoints documented in `./docs/API_CONTRACT.md` (via PR to `prior-mail-docs`)
- [ ] New DB fields documented in `./docs/DATA_MODELS.md` (same)
- [ ] Migration written; `alembic upgrade head && alembic downgrade -1` both work locally
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
make migrate                  # alembic upgrade head
make migration name=add_xxx   # generate new migration
make worker                   # run background sync worker locally

# Submodule
git submodule update --init --recursive    # after fresh clone
git submodule update --remote docs         # pull latest shared specs
```

---

## 13. Open Decisions

LLMs: do **not** assume an answer — ask.

- [ ] Summarizer model: hosted LLM (Anthropic / OpenAI) vs local (Llama / Mistral)?
- [ ] Realtime updates: Supabase Realtime channels vs polling?
- [ ] Queue: in-process asyncio vs Redis-backed (Upstash)?

---

## 14. Owners

- **Syafiq** — Gmail integration, FastAPI scaffolding, infra/deployment
- **Insan** — Model loading & inference integration
- **Faiz** — Phishing detector integration, security review
- **Ridjal** — LangGraph nodes (shared with Faiz)

---

*Last updated: 2026-05-25*
