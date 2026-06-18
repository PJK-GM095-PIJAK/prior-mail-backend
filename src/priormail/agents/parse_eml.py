import email as email_lib
from email import policy

from priormail.agents.state import PipelineState
from priormail.core.errors import EmlParseError


def parse_eml(state: PipelineState) -> dict:
    """Parse raw .eml bytes and extract structured fields."""
    try:
        msg = email_lib.message_from_bytes(state.raw_eml, policy=policy.default)
    except Exception as exc:
        raise EmlParseError(f"Cannot parse .eml: {exc}") from exc

    subject = msg.get("Subject", "") or ""
    sender = msg.get("From", "") or ""
    date_str = msg.get("Date")

    # Parse sender into email + name
    from email.utils import parseaddr, parsedate_to_datetime
    sender_name, sender_email = parseaddr(sender)

    # Parse date
    received_at = None
    if date_str:
        try:
            received_at = parsedate_to_datetime(date_str)
        except Exception:
            pass

    # Extract plain-text body
    body_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body_text = part.get_content() or ""
                break
    else:
        if msg.get_content_type() == "text/plain":
            body_text = msg.get_content() or ""

    snippet = body_text[:200]

    return {
        "subject": subject,
        "sender_email": sender_email,
        "sender_name": sender_name or None,
        "received_at": received_at,
        "body_text": body_text,
        "snippet": snippet,
    }
