"""Unit tests for settings + HF URI parsing."""

from __future__ import annotations

import pytest

from priormail.core.config import Settings, parse_hf_uri


class TestParseHfUri:
    def test_splits_repo_and_version(self) -> None:
        assert parse_hf_uri("hf://insanar/priormail-priority/v2.0") == (
            "insanar/priormail-priority",
            "v2.0",
        )

    def test_missing_version_yields_empty(self) -> None:
        assert parse_hf_uri("hf://insanar/priormail-priority") == (
            "insanar/priormail-priority",
            "",
        )


class TestSettings:
    def test_derived_properties(self) -> None:
        s = Settings(priority_model_uri="hf://insanar/priormail-priority/v2.0")
        assert s.priority_model_repo_id == "insanar/priormail-priority"
        assert s.priority_model_version == "v2.0"

    def test_rejects_non_hf_uri(self) -> None:
        with pytest.raises(ValueError, match="hf://"):
            Settings(priority_model_uri="supabase://models/priority/v1/checkpoint.bin")

    def test_rejects_uri_without_version(self) -> None:
        with pytest.raises(ValueError, match="version subfolder"):
            Settings(priority_model_uri="hf://insanar/priormail-priority")

    def test_cors_origins_from_csv_string(self) -> None:
        s = Settings(cors_origins="http://a.com, http://b.com")  # type: ignore[arg-type]
        assert s.cors_origins == ["http://a.com", "http://b.com"]
