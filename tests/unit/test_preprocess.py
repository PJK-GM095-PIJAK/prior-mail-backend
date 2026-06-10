"""Unit tests for the priority model preprocessing (must match training)."""

from __future__ import annotations

from priormail.services.preprocess import (
    EMAIL_TOKEN,
    SEP,
    URL_TOKEN,
    build_priority_input,
    clean_text,
)


class TestCleanText:
    def test_strips_html_tags(self) -> None:
        assert clean_text("<p>Hello <b>world</b></p>") == "Hello world"

    def test_drops_script_and_style_content(self) -> None:
        out = clean_text("<style>.a{color:red}</style>Hi<script>evil()</script>")
        assert "color" not in out and "evil" not in out
        assert "Hi" in out

    def test_masks_email_addresses(self) -> None:
        assert clean_text("ping me at john.doe@example.com please") == (
            f"ping me at {EMAIL_TOKEN} please"
        )

    def test_masks_urls(self) -> None:
        assert URL_TOKEN in clean_text("see https://evil.example.com/x now")

    def test_email_masked_before_url(self) -> None:
        # An address must be replaced whole, not half-eaten by the URL pattern.
        out = clean_text("contact support@bank.co.id")
        assert out == f"contact {EMAIL_TOKEN}"

    def test_collapses_whitespace(self) -> None:
        assert clean_text("a\n\n  b\t c") == "a b c"

    def test_none_is_empty(self) -> None:
        assert clean_text(None) == ""


class TestBuildPriorityInput:
    def test_format_is_subject_sep_body(self) -> None:
        assert build_priority_input("Hi", "there") == f"Hi {SEP} there"

    def test_cleans_both_fields(self) -> None:
        out = build_priority_input("<b>Subj</b>", "mail me a@b.com")
        assert out == f"Subj {SEP} mail me {EMAIL_TOKEN}"

    def test_handles_none_fields(self) -> None:
        assert build_priority_input(None, None) == f" {SEP} "
