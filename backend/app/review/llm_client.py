"""
How this works / why it is safe:
This module encapsulates HTTP client interactions with external LLM providers
(Groq and Google Gemini) with strict security barriers:
1. Strict Prompt Injection Isolation: All user input, ledger memos, and untrusted
   counterparty text are sanitized and strictly quarantined inside <untrusted_memo>
   and <untrusted_user_text> XML boundaries.
2. System Prompt Armor: The system prompt explicitly instructs the LLM that it is
   strictly READ-ONLY, cannot move money or invoke commands, and must ignore instructions
   found within untrusted data tags.
3. Resilience & Fallback: If network calls fail, timeout, or keys are absent,
   it raises or returns cleanly to allow immediate deterministic synthesis fallback.
4. No Ledger Write Capability: This module only generates text responses.
"""

import re

import httpx

from app.config import settings
from app.logging import logger

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def sanitize_untrusted_text(text: str) -> str:
    """Sanitize user-provided text to prevent prompt injection and tag breakout."""
    if not text:
        return ""
    # Strip dangerous control characters and neutralize XML/tag breakout attempts
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    clean = clean.replace("<", "&lt;").replace(">", "&gt;")
    return clean[:2000]


def call_groq_api(system_prompt: str, user_prompt: str, api_key: str, model: str) -> str:
    """Call Groq API using standard OpenAI-compatible completions endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(GROQ_ENDPOINT, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"]).strip()


def call_gemini_api(system_prompt: str, user_prompt: str, api_key: str, model: str) -> str:
    """Call Google Gemini REST API."""
    url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    combined_prompt = f"{system_prompt}\n\n---\nUSER INQUIRY AND CONTEXT:\n{user_prompt}"
    payload = {
        "contents": [
            {
                "parts": [{"text": combined_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1200,
        },
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts and "text" in parts[0]:
                return str(parts[0]["text"]).strip()
        raise ValueError("Invalid response format from Gemini API")


def synthesize_with_llm(
    system_prompt: str,
    context_text: str,
    user_query: str,
) -> tuple[str | None, str | None, str | None]:
    """Execute LLM call across configured providers (Groq -> Gemini -> None).

    Returns:
        (reply_text, provider_name, model_name) or (None, None, None) on failure/absence.
    """
    if not settings.LLM_ENABLED:
        return None, None, None

    # Construct quarantined user payload
    sanitized_query = sanitize_untrusted_text(user_query)
    user_prompt = (
        f"{context_text}\n\n"
        f"<untrusted_user_query>\n{sanitized_query}\n</untrusted_user_query>"
    )

    # 1. Try Groq if configured
    groq_key = settings.GROQ_API_KEY or (settings.LLM_API_KEY if settings.LLM_PROVIDER == "groq" else None)
    if groq_key and settings.LLM_PROVIDER in ("auto", "groq"):
        try:
            reply = call_groq_api(system_prompt, user_prompt, groq_key, settings.GROQ_MODEL)
            return reply, "groq", settings.GROQ_MODEL
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            logger.info("groq_synthesis_fallback", error_type=type(e).__name__, status_code=status)

    # 2. Try Gemini if configured
    gemini_key = settings.GEMINI_API_KEY or (settings.LLM_API_KEY if settings.LLM_PROVIDER == "gemini" else None)
    if gemini_key and settings.LLM_PROVIDER in ("auto", "gemini"):
        try:
            reply = call_gemini_api(system_prompt, user_prompt, gemini_key, settings.GEMINI_MODEL)
            return reply, "gemini", settings.GEMINI_MODEL
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            logger.info("gemini_synthesis_fallback", error_type=type(e).__name__, status_code=status)

    return None, None, None
