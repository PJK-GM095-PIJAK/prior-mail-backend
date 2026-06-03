# tests/unit/__init__.py
# ─────────────────────────────────────────────────────────────
# Unit tests — test individual functions/classes in isolation.
#
# Naming convention: test_<module>.py
# One test class per scenario.
#
# Focus areas:
# - agents/ nodes (each node independently, with mock state)
# - services/ business logic (with mocked DB/API)
# - models/ schema validation
# - core/errors.py exception mapping
#
# Example files to create:
#   test_preprocess.py    → test HTML stripping, language detection
#   test_classify.py      → test priority classification with mock model
#   test_phishing.py      → test phishing detection with mock model
#   test_email_service.py → test CRUD logic with mock DB
#   test_schemas.py       → test Pydantic validation
# ─────────────────────────────────────────────────────────────
