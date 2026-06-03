# ─────────────────────────────────────────────────────────────
# Makefile — common development commands
# See CLAUDE.md §12 for command reference
# ─────────────────────────────────────────────────────────────

.PHONY: install dev test lint format migrate migration worker clean

# Install all dependencies (including dev)
install:
	uv pip install -e ".[dev]"

# Run development server with hot reload
dev:
	uvicorn priormail.main:app --reload --port 8000

# Run all tests with coverage
test:
	pytest --cov=priormail --cov-report=term-missing

# Run linter + type checker
lint:
	ruff check src/ tests/
	mypy --strict src/

# Auto-format code
format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

# Run database migrations
migrate:
	alembic upgrade head

# Generate a new migration (usage: make migration name=add_xxx)
migration:
	alembic revision --autogenerate -m "$(name)"

# Run background sync worker locally
worker:
	python -m priormail.workers.sync_worker

# Clean generated files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf .ruff_cache htmlcov .coverage
