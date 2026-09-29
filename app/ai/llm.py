"""
app/ai/llm.py
-------------
Minimal LLM client for the AI HR Assistant MVP.

Connects to an OpenAI-compatible completion API using httpx without heavy
framework dependencies (e.g. LangChain).

Configuration via environment variables:
- LLM_API_KEY: Provider authentication key.
- LLM_MODEL: Model name (default: "gpt-4o-mini").
- LLM_BASE_URL: Provider base endpoint (default: "https://api.openai.com/v1").
- LLM_TIMEOUT: Request timeout in seconds (default: 30.0).
"""

import os
from typing import Optional

import httpx
from dotenv import dotenv_values


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base exception for all LLM client errors."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when required LLM configuration (such as API key) is missing."""
    pass


class LLMProviderError(LLMError):
    """Raised when the LLM provider fails to process the request."""
    pass


# ---------------------------------------------------------------------------
# Client Configuration & Generation
# ---------------------------------------------------------------------------

def get_llm_config() -> dict:
    """Retrieve current LLM configuration from environment, falling back to .env file."""
    vals = dotenv_values(".env") if os.path.exists(".env") else {}
    
    api_key = os.getenv("LLM_API_KEY")
    if api_key is None:
        api_key = vals.get("LLM_API_KEY", "")

    model = os.getenv("LLM_MODEL")
    if model is None:
        model = vals.get("LLM_MODEL", "openai/gpt-4o-mini")

    base_url = os.getenv("LLM_BASE_URL")
    if base_url is None:
        base_url = vals.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")

    timeout_str = os.getenv("LLM_TIMEOUT")
    if timeout_str is None:
        timeout_str = vals.get("LLM_TIMEOUT", "30.0")

    return {
        "api_key": api_key.strip(),
        "model": model.strip(),
        "base_url": base_url.strip().rstrip("/"),
        "timeout": float(timeout_str),
    }


def generate_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 500,
) -> str:
    """
    Send prompt to the configured LLM provider and return generated text.

    Args:
        prompt: User question with context.
        system_prompt: Optional system instruction for grounding/anti-hallucination.
        model: Optional override for the target model.
        temperature: Sampling temperature (low for grounded factual answers).
        max_tokens: Upper bound on output tokens.

    Raises:
        LLMConfigurationError: If LLM_API_KEY is missing.
        LLMProviderError: On network, HTTP, timeout, or schema parsing errors.

    Returns:
        str: Generated natural language answer.
    """
    config = get_llm_config()
    api_key = config["api_key"]

    if not api_key:
        raise LLMConfigurationError("LLM_API_KEY environment variable is not configured.")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AI HR Assistant",
    }
    payload = {
        "model": model or config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        with httpx.Client(timeout=config["timeout"]) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices")
        if not choices or not isinstance(choices, list):
            raise LLMProviderError(f"Unexpected response format from LLM provider: {data}")

        message = choices[0].get("message", {})
        content = message.get("content")
        if content is None:
            raise LLMProviderError(f"LLM response choices contained no content: {choices[0]}")

        return content.strip()

    except httpx.HTTPStatusError as exc:
        raise LLMProviderError(
            f"LLM provider HTTP error: status {exc.response.status_code} - {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise LLMProviderError(f"LLM provider network error: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMProviderError(f"Failed to parse LLM provider response: {exc}") from exc
    except LLMError:
        raise
    except Exception as exc:
        raise LLMProviderError(f"Unexpected error communicating with LLM provider: {exc}") from exc
