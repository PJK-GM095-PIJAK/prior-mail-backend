# PriorMail Backend

FastAPI backend for PriorMail. See [CLAUDE.md](CLAUDE.md) for the full project guide.

## Quick start

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"        # or: make install
cp .env.example .env.local        # adjust if needed
make dev                          # uvicorn on :8000 (downloads the model on first boot)
```

The priority model (DistilBERT, hosted on the HuggingFace Hub) is loaded once at
startup. If it fails to load, the app refuses to boot. Configure it via
`PRIORITY_MODEL_URI` (default `hf://insanar/priormail-priority/v2.0`).

## Priority classification endpoint

> Standalone classify slice for the frontend while the full emails/sync pipeline
> is built. Not yet in `docs/API_CONTRACT.md` — see the integration follow-ups.

### `GET /api/v1/_health/models`
Reports loaded model versions; `503` if a model failed to load.
```json
{ "data": { "priority": "v2.0" }, "error": null, "meta": {} }
```

### `POST /api/v1/classify/priority`
Classifies an email's priority. At least one of `subject`/`body` must be non-empty.

**Request:** `{ "subject": "string", "body": "string" }`

**Response 200:**
```json
{
  "data": { "priority": "urgent", "priority_confidence": 0.86, "model_version": "v2.0" },
  "error": null,
  "meta": {}
}
```
`priority` is one of `urgent | high | normal | low`. Errors use the standard
envelope (`validation.invalid_field` → 400, `service.model_unavailable` → 503).

### Calling it from the frontend (React)

CORS allows `http://localhost:3000` and `:5173` by default (set `CORS_ORIGINS` to change).

```js
const res = await fetch("http://localhost:8000/api/v1/classify/priority", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ subject, body }),
});
const { data, error } = await res.json();
if (error) throw new Error(error.code);
// data => { priority, priority_confidence, model_version }
```

## Development

```bash
make lint     # ruff check + mypy --strict
make test     # pytest + coverage
make format   # ruff format + autofix
```
