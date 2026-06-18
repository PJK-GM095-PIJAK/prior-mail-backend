# tests/integration/__init__.py
# ─────────────────────────────────────────────────────────────
# Integration tests — test full flows across multiple components.
#
# Naming convention: test_<flow>.py
#
# Focus areas:
# - Full LangGraph pipeline (parse → classify → summarize → extract)
# - API endpoint happy paths (via httpx test client)
# - Health endpoint reporting
# ─────────────────────────────────────────────────────────────
