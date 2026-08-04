"""Shared LLM client for structured extraction.

xAI Grok through the OpenAI-compatible LangChain client — the same arrangement
as the sibling cockpits (FastPPM, FastClinic). Honours the existing
``MODEL_PROVIDER`` / ``MODEL_NAME`` env vars this repo already uses for the chat
rail, so one key configures both.

The streaming chat rail in web/ai.py stays on raw httpx; it needs token-level
streaming, which is not what this client is for.
"""
from __future__ import annotations

import os

# OpenAI-compatible endpoints, reachable with langchain-openai.
BASE_URLS = {
    "xai": os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
    "openai": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
}
KEY_VARS = {"xai": "XAI_API_KEY", "openai": "OPENAI_API_KEY"}

_llm = None


def provider() -> str:
    p = os.getenv("MODEL_PROVIDER", "xai").lower()
    return p if p in BASE_URLS else "xai"


def model_name() -> str:
    return os.getenv("MODEL_NAME", "grok-4-1-fast-reasoning")


def api_key() -> str:
    return os.getenv(KEY_VARS[provider()], "")


def available() -> bool:
    return bool(api_key())


def unavailable_reason() -> str:
    p = provider()
    return (f"No {KEY_VARS[p]} configured, so CV extraction is disabled. "
            f"Add it to .env and restart — the rest of the ATS works without it.")


def get_llm(*, temperature: float = 0.1, timeout: int = 120):
    """Lazily build the chat client. Raises if no key is configured."""
    global _llm
    if _llm is None:
        if not available():
            raise RuntimeError(unavailable_reason())
        from langchain_openai import ChatOpenAI
        p = provider()
        _llm = ChatOpenAI(model=model_name(), api_key=api_key(), base_url=BASE_URLS[p],
                          temperature=temperature, timeout=timeout)
    return _llm


def reset():
    """Drop the cached client — used by tests and after an env change."""
    global _llm
    _llm = None
