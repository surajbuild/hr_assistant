"""
tests/test_llm.py
-----------------
Unit tests for the minimal LLM client in app/ai/llm.py.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

import httpx

from app.ai.llm import (
    LLMConfigurationError,
    LLMProviderError,
    generate_response,
    get_llm_config,
)

SEP = "-" * 55
passed = 0
failed = 0


def chk(ok: bool, ok_msg: str, fail_msg: str):
    global passed, failed
    if ok:
        print(f"    PASS - {ok_msg}")
        passed += 1
    else:
        print(f"    FAIL - {fail_msg}")
        failed += 1


try:
    print(SEP)
    print("  app/ai/llm.py - Unit Test Suite")
    print(SEP)

    # -----------------------------------------------------------------------
    # [1] Configuration without API Key raises LLMConfigurationError
    # -----------------------------------------------------------------------
    print("\n[1] Missing API Key Handling")
    with patch.dict(os.environ, {"LLM_API_KEY": ""}):
        try:
            generate_response(prompt="Hello")
            chk(False, "Should have raised LLMConfigurationError", "No exception raised")
        except LLMConfigurationError:
            chk(True, "Missing LLM_API_KEY raises LLMConfigurationError", "")

    # -----------------------------------------------------------------------
    # [2] Successful response parsing
    # -----------------------------------------------------------------------
    print("\n[2] Successful Response Parsing")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Aman was present for 22 days in August 2024.",
                }
            }
        ]
    }
    fake_resp.raise_for_status.return_value = None

    with patch.dict(os.environ, {"LLM_API_KEY": "fake-test-key"}), \
         patch("httpx.Client.post", return_value=fake_resp) as mock_post:
        ans = generate_response(
            prompt="How many days was Aman present?",
            system_prompt="You are an HR assistant",
        )
        chk(ans == "Aman was present for 22 days in August 2024.",
            "Correctly extracted assistant content from choices", f"Got: {ans}")
        # Verify call payload
        call_kwargs = mock_post.call_args[1]
        chk(call_kwargs["headers"]["Authorization"] == "Bearer fake-test-key",
            "Authorization header set correctly", "Auth header mismatch")
        chk(len(call_kwargs["json"]["messages"]) == 2,
            "System prompt and user prompt formatted as messages", "Messages mismatch")

    # -----------------------------------------------------------------------
    # [3] HTTP Error Handling
    # -----------------------------------------------------------------------
    print("\n[3] HTTP Error Handling")
    err_resp = MagicMock()
    err_resp.status_code = 401
    err_resp.text = '{"error": "Invalid API key"}'
    http_err = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=err_resp)

    with patch.dict(os.environ, {"LLM_API_KEY": "invalid-key"}), \
         patch("httpx.Client.post", side_effect=http_err):
        try:
            generate_response(prompt="Hello")
            chk(False, "Should have raised LLMProviderError", "No exception raised")
        except LLMProviderError as exc:
            chk("status 401" in str(exc), "HTTP 401 wrapped in LLMProviderError", f"Got: {exc}")

    # -----------------------------------------------------------------------
    # [4] Network / Timeout Error Handling
    # -----------------------------------------------------------------------
    print("\n[4] Network / Timeout Error Handling")
    net_err = httpx.ConnectTimeout("Connection timed out after 30s")

    with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}), \
         patch("httpx.Client.post", side_effect=net_err):
        try:
            generate_response(prompt="Hello")
            chk(False, "Should have raised LLMProviderError", "No exception raised")
        except LLMProviderError as exc:
            chk("network error" in str(exc).lower() or "timeout" in str(exc).lower(),
                "Network timeout wrapped in LLMProviderError", f"Got: {exc}")

    # -----------------------------------------------------------------------
    # [5] Malformed Provider Response
    # -----------------------------------------------------------------------
    print("\n[5] Malformed Provider Response")
    bad_resp = MagicMock()
    bad_resp.json.return_value = {"choices": []}  # Empty choices
    bad_resp.raise_for_status.return_value = None

    with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}), \
         patch("httpx.Client.post", return_value=bad_resp):
        try:
            generate_response(prompt="Hello")
            chk(False, "Should have raised LLMProviderError", "No exception raised")
        except LLMProviderError as exc:
            chk("unexpected response format" in str(exc).lower(),
                "Empty choices array handled as LLMProviderError", f"Got: {exc}")

    print("\n" + SEP)
    print(f"  Results: {passed} passed, {failed} failed")
    print(SEP)

except Exception as exc:
    print(f"\n[ERROR] Exception occurred: {exc}")
    import traceback
    traceback.print_exc()
    failed += 1

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
