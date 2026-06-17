from groq import Groq

from priormail.core.config import get_settings


def build_llm_client() -> Groq:
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key)
