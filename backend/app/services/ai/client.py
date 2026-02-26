"""Groq API Client — all AI calls go through this module.

Uses httpx (already available via FastAPI/uvicorn) for REST calls.
No Groq SDK required.

Constraints:
- Timeout: ≤10s
- Retries: max 2
- All calls logged
- Raw responses NEVER exposed outside this module
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"   # fast, cheap, structured output capable

REQUEST_TIMEOUT = 10.0   # seconds — hard limit
MAX_RETRIES = 2
RETRY_DELAY = 1.0        # seconds between retries


class GroqClientError(Exception):
    """Raised when all Groq API attempts fail."""
    pass


class GroqClient:
    """Stateless Groq REST client. All calls are synchronous (httpx)."""

    @staticmethod
    def chat_json(
        system_prompt: str,
        user_message: str,
        api_key: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> Optional[dict]:
        """Send a chat completion request to Groq and parse JSON response.

        Returns parsed dict on success, None on failure.
        Never raises — all errors are logged and caught.
        """
        if not api_key:
            logger.error("GroqClient: GROQ_API_KEY is empty — cannot call API")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                    resp = client.post(GROQ_CHAT_URL, headers=headers, json=payload)

                elapsed = round(time.monotonic() - t0, 2)
                logger.info(f"GroqClient: attempt {attempt} — {resp.status_code} in {elapsed}s")

                if resp.status_code == 429:
                    # Rate limited — wait and retry
                    logger.warning("GroqClient: rate limited (429) — retrying")
                    time.sleep(RETRY_DELAY * attempt)
                    continue

                if resp.status_code != 200:
                    logger.error(f"GroqClient: HTTP {resp.status_code} — {resp.text[:200]}")
                    last_error = f"HTTP {resp.status_code}"
                    time.sleep(RETRY_DELAY)
                    continue

                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                if not content:
                    logger.error("GroqClient: empty content in response")
                    last_error = "Empty content"
                    continue

                # Parse JSON from response
                parsed = json.loads(content)
                logger.info(f"GroqClient: parsed JSON successfully ({len(content)} chars)")
                return parsed

            except json.JSONDecodeError as e:
                logger.error(f"GroqClient: JSON parse error — {e}")
                last_error = f"JSON parse: {e}"
            except httpx.TimeoutException:
                elapsed = round(time.monotonic() - t0, 2)
                logger.error(f"GroqClient: timeout after {elapsed}s (limit={REQUEST_TIMEOUT}s)")
                last_error = "Timeout"
            except httpx.HTTPError as e:
                logger.error(f"GroqClient: HTTP error — {e}")
                last_error = f"HTTP error: {e}"
            except Exception as e:
                logger.error(f"GroqClient: unexpected error — {e}")
                last_error = f"Unexpected: {e}"

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        logger.error(f"GroqClient: all {MAX_RETRIES} attempts failed — last error: {last_error}")
        return None
