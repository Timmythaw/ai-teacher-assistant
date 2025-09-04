"""
AutoGen model configuration and helpers.

Centralizes provider credentials, per-role model selection, default temperatures,
max tokens, timeouts, and fallback chains. Builds AutoGen-compatible llm_config
dicts for agents (planner/orchestra and specialists).

This module intentionally reads from environment variables (with sensible
defaults) and reuses credentials from core.config.

Env overrides (optional):
- ORCHESTRA_MODEL, LESSON_MODEL, ASSESSMENT_MODEL, TIMETABLE_MODEL, EMAIL_MODEL
- ORCHESTRA_TEMPERATURE, LESSON_TEMPERATURE, ASSESSMENT_TEMPERATURE,
  TIMETABLE_TEMPERATURE, EMAIL_TEMPERATURE
- ORCHESTRA_MAX_TOKENS, LESSON_MAX_TOKENS, ASSESSMENT_MAX_TOKENS,
  TIMETABLE_MAX_TOKENS, EMAIL_MAX_TOKENS
- ORCHESTRA_TIMEOUT_SEC, LESSON_TIMEOUT_SEC, ASSESSMENT_TIMEOUT_SEC,
  TIMETABLE_TIMEOUT_SEC, EMAIL_TIMEOUT_SEC
- FALLBACK_MODEL_1, FALLBACK_MODEL_2, FALLBACK_MODEL_3 (global optional fallbacks)
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, TypedDict

try:
    # Reuse global API credentials and base URL used by the rest of the app
    from core.config import AI_ML_API_KEY as API_KEY, AI_ML_BASE_URL as API_BASE_URL
except Exception:
    # Defer hard failure; callers can check has_api_credentials() and fail fast.
    API_KEY = os.getenv("AI_ML_API_KEY")
    API_BASE_URL = os.getenv("AI_ML_BASE_URL", "https://api.aimlapi.com/v1")


class LLMConfig(TypedDict, total=False):
    # AutoGen-compatible llm_config
    config_list: List[Dict[str, str]]
    temperature: float
    timeout: int
    max_tokens: int
    cache_seed: int
    # passthroughs
    stream: bool


# --- Defaults ---

DEFAULT_PRIMARY: Dict[str, str] = {
    # planner/router
    "orchestra": os.getenv("ORCHESTRA_MODEL")
    or os.getenv("GPT_MODEL")
    or "openai/gpt-5-chat-latest",
    # specialists
    "lesson": os.getenv("LESSON_MODEL")
    or os.getenv("GPT_MODEL")
    or "openai/gpt-5-chat-latest",
    "assessment": os.getenv("ASSESSMENT_MODEL")
    or os.getenv("GPT_MODEL")
    or "openai/gpt-5-chat-latest",
    "timetable": os.getenv("TIMETABLE_MODEL")
    or os.getenv("LLAMA_MODEL")
    or "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "email": os.getenv("EMAIL_MODEL")
    or os.getenv("GPT_MODEL")
    or "openai/gpt-5-chat-latest",
}

DEFAULT_TEMPS: Dict[str, float] = {
    "orchestra": float(os.getenv("ORCHESTRA_TEMPERATURE", "0.2")),
    "lesson": float(os.getenv("LESSON_TEMPERATURE", "0.4")),
    "assessment": float(os.getenv("ASSESSMENT_TEMPERATURE", "0.4")),
    "timetable": float(os.getenv("TIMETABLE_TEMPERATURE", "0.1")),
    "email": float(os.getenv("EMAIL_TEMPERATURE", "0.3")),
}

DEFAULT_MAX_TOKENS: Dict[str, int] = {
    "orchestra": int(os.getenv("ORCHESTRA_MAX_TOKENS", "2000")),
    "lesson": int(os.getenv("LESSON_MAX_TOKENS", "4000")),
    "assessment": int(os.getenv("ASSESSMENT_MAX_TOKENS", "3000")),
    "timetable": int(os.getenv("TIMETABLE_MAX_TOKENS", "1000")),
    "email": int(os.getenv("EMAIL_MAX_TOKENS", "1200")),
}

DEFAULT_TIMEOUTS: Dict[str, int] = {
    "orchestra": int(os.getenv("ORCHESTRA_TIMEOUT_SEC", "60")),
    "lesson": int(os.getenv("LESSON_TIMEOUT_SEC", "90")),
    "assessment": int(os.getenv("ASSESSMENT_TIMEOUT_SEC", "90")),
    "timetable": int(os.getenv("TIMETABLE_TIMEOUT_SEC", "45")),
    "email": int(os.getenv("EMAIL_TIMEOUT_SEC", "45")),
}

# Per-role tailored fallback preferences; primary will be prepended.
ROLE_FALLBACKS: Dict[str, List[str]] = {
    "orchestra": [
        "openai/gpt-5-chat-latest",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "deepseek/deepseek-chat-v3.1",
    ],
    "lesson": [
        "openai/gpt-5-chat-latest",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "deepseek/deepseek-chat-v3.1",
    ],
    "assessment": [
        "openai/gpt-5-chat-latest",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "deepseek/deepseek-chat-v3.1",
    ],
    "timetable": [
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "openai/gpt-5-chat-latest",
    ],
    "email": [
        "openai/gpt-5-chat-latest",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ],
}


def _global_fallbacks() -> List[str]:
    """Collect optional global fallbacks from env, preserving order and uniqueness."""
    envs = [os.getenv("FALLBACK_MODEL_1"), os.getenv("FALLBACK_MODEL_2"), os.getenv("FALLBACK_MODEL_3")]
    out: List[str] = []
    for m in envs:
        if m and m not in out:
            out.append(m)
    return out


def has_api_credentials() -> bool:
    """Return True if provider API credentials appear to be available."""
    return bool(API_KEY and API_BASE_URL)


def get_primary_model(role: str) -> str:
    """Return primary model for the given agent role."""
    return DEFAULT_PRIMARY.get(role, DEFAULT_PRIMARY["orchestra"])  # type: ignore[index]


def get_fallback_models(role: str) -> List[str]:
    """Return primary + role and global fallback chain with deduplication."""
    primary = get_primary_model(role)
    chain = [primary]
    for m in ROLE_FALLBACKS.get(role, []):
        if m not in chain:
            chain.append(m)
    for m in _global_fallbacks():
        if m not in chain:
            chain.append(m)
    return chain


def get_config_list_for_role(role: str) -> List[Dict[str, str]]:
    """
    Build AutoGen-compatible config_list for a role with fallbacks prioritized.
    Each entry is OpenAI-compatible (AIMLAPI is an OpenAI-compatible gateway).
    """
    configs: List[Dict[str, str]] = []
    for model in get_fallback_models(role):
        configs.append(
            {
                "model": model,
                "api_key": API_KEY or "",  # callers should verify has_api_credentials()
                "base_url": API_BASE_URL or "https://api.aimlapi.com/v1",
                # "api_type": "openai",  # optional hint
            }
        )
    return configs


def get_autogen_llm_config(role: str, *, temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                           timeout: Optional[int] = None, cache_seed: int = 42, stream: bool = False) -> LLMConfig:
    """
    Return an AutoGen llm_config for the given role. Callers can override
    temperature, max_tokens, timeout if needed.
    """
    llm: LLMConfig = {
        "config_list": get_config_list_for_role(role),
        "temperature": float(temperature if temperature is not None else DEFAULT_TEMPS.get(role, 0.2)),
        "max_tokens": int(max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS.get(role, 2000)),
        "timeout": int(timeout if timeout is not None else DEFAULT_TIMEOUTS.get(role, 60)),
        "cache_seed": int(cache_seed),
        "stream": bool(stream),
    }
    return llm


__all__ = [
    "API_BASE_URL",
    "API_KEY",
    "has_api_credentials",
    "get_primary_model",
    "get_fallback_models",
    "get_config_list_for_role",
    "get_autogen_llm_config",
    "DEFAULT_TEMPS",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUTS",
]
