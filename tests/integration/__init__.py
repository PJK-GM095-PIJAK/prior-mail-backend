# tests/integration/__init__.py
# ─────────────────────────────────────────────────────────────
# Integration tests — test full flows across multiple components.
#
# Naming convention: test_<flow>.py
#
# Focus areas:
# - Full LangGraph pipeline (preprocess → ... → persist)
# - API endpoint happy paths (via httpx test client)
# - Gmail sync flow (with mocked Gmail API)
# - Auth flow (with mocked Supabase)
#
# Example files to create:
#   test_pipeline.py      → test full email processing pipeline
#   test_email_api.py     → test email endpoints end-to-end
#   test_sync_flow.py     → test sync trigger flow
#   test_auth_flow.py     → test OAuth callback flow
# ─────────────────────────────────────────────────────────────
