"""Text preprocessing for the priority model's input.

Ported from ``prior-mail-model/src/data/preprocess.py`` — this MUST stay in
sync with the training-time preprocessing. The model was trained on a specific
preprocessed string, not raw email; feeding raw text silently produces wrong
predictions (BACKEND_INTEGRATION_GUIDE §3, ML_PIPELINE.md §2).

Pipeline (order matters):
    1. Strip HTML (drop <script>/<style> with content, strip tags, unescape).
    2. Mask emails with ``[EMAIL]`` (before URLs, so an address isn't half-eaten).
    3. Mask URLs with ``[URL]``.
    4. Collapse whitespace.
Token-level truncation to the 512 budget happens at tokenization time.

Input format (priority): ``{cleaned_subject} [SEP] {cleaned_body}``.

The upstream module uses the third-party ``regex`` library; these patterns use
no ``regex``-only features, so we use the stdlib ``re`` here to avoid a new
dependency.
"""

from __future__ import annotations

import html
import re

URL_TOKEN = "[URL]"
EMAIL_TOKEN = "[EMAIL]"
# BERT's separator. The tokenizer maps this string to its real [SEP] id.
SEP = "[SEP]"

# --- Patterns (compiled once) ---------------------------------------------
# Drop <script>/<style> blocks *with their content* before stripping tags,
# so JS/CSS text doesn't leak into the cleaned body.
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
# Any remaining HTML/XML tag.
_TAG_RE = re.compile(r"<[^>]+>")
# Email addresses. Run BEFORE the URL pattern so an address isn't half-eaten.
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# URLs: http(s)://… , www.… , and bare domains with a common TLD.
_URL_RE = re.compile(
    r"(?:https?://|www\.)\S+"
    # bare domains: one-or-more dotted labels then a known TLD, e.g. example.com/x
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|id|co|io|gov|edu)\b\S*",
    re.IGNORECASE,
)
# Runs of any whitespace (incl. newlines/tabs) -> a single space.
_WS_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Remove HTML: drop script/style blocks, strip tags, unescape entities."""
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    return html.unescape(text)


def clean_text(text: str | None) -> str:
    """Apply steps 1–4 of the pipeline to one raw field.

    Order matters: HTML strip -> emails -> URLs -> collapse whitespace.
    ``None`` is treated as an empty string.
    """
    if not text:
        return ""
    text = strip_html(text)
    text = _EMAIL_RE.sub(EMAIL_TOKEN, text)
    text = _URL_RE.sub(URL_TOKEN, text)
    return _WS_RE.sub(" ", text).strip()


def build_priority_input(subject: str | None, body: str | None) -> str:
    """Assemble the priority model's single-string input.

    ``{cleaned_subject} [SEP] {cleaned_body}``. Both fields are cleaned first;
    token-level truncation happens at tokenization time (ML_PIPELINE.md §2).
    """
    return f"{clean_text(subject)} {SEP} {clean_text(body)}"
