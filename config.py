import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# LLM API config (OpenAI-compatible endpoint)
LLM_CONFIG = {
    "api_key": os.getenv("LLM_API_KEY", ""),
    "model_name": os.getenv("LLM_MODEL_NAME", "deepseek-v4-flash"),
    "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    "temperature": _env_float("LLM_TEMPERATURE", 0.7),
    "max_tokens": _env_int("LLM_MAX_TOKENS", 8192),
    "timeout": _env_float("LLM_TIMEOUT", 60.0),
    "max_retries": _env_int("LLM_MAX_RETRIES", 2),
}

# Mem0 API config (Long-term memory)
MEM0_CONFIG = {
    "api_key": os.getenv("MEM0_API_KEY", ""),
}

# Redis config (optional recent conversations / short-term persistence)
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": _env_int("REDIS_PORT", 6379),
    "db": _env_int("REDIS_DB", 0),
    "password": os.getenv("REDIS_PASSWORD") or None,
}
