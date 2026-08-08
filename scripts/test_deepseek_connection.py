#!/usr/bin/env python3
"""
Test DeepSeek API connectivity using project LLM config.

Usage:
    python scripts/test_deepseek_connection.py
"""
import asyncio
import json
import sys
from pathlib import Path

from loguru import logger
from openai import AsyncOpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import LLM_CONFIG  # noqa: E402


async def main() -> int:
    api_key = LLM_CONFIG.get("api_key", "")
    base_url = LLM_CONFIG.get("base_url", "")
    model_name = LLM_CONFIG.get("model_name", "")
    timeout = float(LLM_CONFIG.get("timeout", 20.0))

    if not api_key:
        print("LLM_API_KEY is empty.")
        return 2

    print("Testing DeepSeek connection with:")
    print(json.dumps(
        {
            "base_url": base_url,
            "model_name": model_name,
            "timeout": timeout,
        },
        ensure_ascii=False,
        indent=2,
    ))

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=0,
    )

    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a connectivity test."},
                {"role": "user", "content": "ping"},
            ],
            max_tokens=128,
            temperature=0,
        )
        choice = response.choices[0]
        content = choice.message.content or ""
        print("Connection OK.")
        print(f"finish_reason: {choice.finish_reason}")
        print(f"reply: {content}")
        return 0
    except Exception as exc:
        logger.exception("DeepSeek connectivity test failed")
        print(f"Connection FAILED: {exc!r}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
