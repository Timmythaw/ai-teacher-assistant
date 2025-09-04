import os
from dotenv import load_dotenv

# Always load .env from project root
load_dotenv(override=True)

# OpenAI-compatible AIMLAPI backend
AI_ML_API_KEY = os.getenv("AI_ML_API_KEY")
AI_ML_BASE_URL = os.getenv("AI_ML_BASE_URL", "https://api.aimlapi.com/v1")

if not AI_ML_API_KEY:
    raise ValueError("Missing AI_ML_API_KEY. Please add it to your .env file")

# Per-agent model defaults (planner vs. workers)
PLANNER_MODEL = os.getenv("PLANNER_MODEL", os.getenv("GPT_MODEL", "openai/gpt-5-chat-latest"))
WORKER_MODEL = os.getenv("WORKER_MODEL", os.getenv("LLAMA_MODEL", "meta/llama-3.1-70b-instruct"))

# Optional tuning
PLANNER_TEMPERATURE = float(os.getenv("PLANNER_TEMPERATURE", "0.2"))
WORKER_TEMPERATURE = float(os.getenv("WORKER_TEMPERATURE", "0.5"))

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# Escalation toggle: use higher-end model for complex tasks
USE_COMPLEX_MODEL = os.getenv("USE_COMPLEX_MODEL", "false").lower() in {"1", "true", "yes"}
COMPLEX_MODEL = os.getenv("COMPLEX_MODEL", "openai/gpt-5-chat-latest")

def select_model(is_complex: bool = False) -> str:
    if is_complex and USE_COMPLEX_MODEL:
        return COMPLEX_MODEL
    return PLANNER_MODEL

__all__ = [
    "AI_ML_API_KEY",
    "AI_ML_BASE_URL",
    "PLANNER_MODEL",
    "WORKER_MODEL",
    "PLANNER_TEMPERATURE",
    "WORKER_TEMPERATURE",
    "REQUEST_TIMEOUT",
    "MAX_TOKENS",
    "USE_COMPLEX_MODEL",
    "COMPLEX_MODEL",
    "select_model",
]