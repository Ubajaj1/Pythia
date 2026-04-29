"""Anthropic LLM client — drop-in replacement for OllamaClient."""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from pythia.config import ANTHROPIC_MODEL
from pythia.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_MAX_TOKENS = 4096
_MAX_RETRIES = 10

# Status codes that warrant a retry with backoff. Everything else is treated as
# a terminal error and raised immediately with a helpful message.
#   429 — rate limit (honor Retry-After if present)
#   500 — transient API error
#   502 — bad gateway (rare, but seen behind Cloudflare)
#   503 — service unavailable
#   504 — timeout inside Anthropic's stack
#   529 — overloaded
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504, 529}


class AnthropicError(RuntimeError):
    """Terminal Anthropic API error — don't retry, surface to the user."""


def _extract_balanced_json(text: str) -> str | None:
    """Find and return the first balanced JSON object in text.

    Tracks brace depth while respecting string literals and escape sequences,
    so it won't be fooled by prose containing stray braces after the JSON,
    or by braces inside strings. Returns None if no complete object is found
    (e.g. the response was truncated mid-JSON).
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_error_body(response: httpx.Response) -> tuple[str, str]:
    """Extract (error_type, message) from an Anthropic error response.

    Anthropic error shape: {"type": "error", "error": {"type": "...", "message": "..."}}
    Falls back to HTTP status text if the body isn't the expected shape.
    """
    try:
        body = response.json()
    except Exception:
        return "unknown", response.text or f"HTTP {response.status_code}"

    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("type", "unknown")), str(err.get("message", ""))
    return "unknown", str(body)


def _format_terminal_error(status: int, err_type: str, message: str, model: str) -> str:
    """Build a user-facing error message for non-retryable errors."""
    # Add a hint based on the error type to help the user self-diagnose
    hints = {
        "authentication_error": "Check ANTHROPIC_API_KEY in your .env.",
        "billing_error": "Check your billing/payment status in the Anthropic Console.",
        "permission_error": "Your API key doesn't have access to this resource.",
        "not_found_error": (
            f"Model {model!r} was not found. "
            "Check ANTHROPIC_MODEL — common valid names: "
            "claude-haiku-4-5-20251001, claude-sonnet-4-5, claude-opus-4-5."
        ),
        "request_too_large": (
            "The prompt exceeded the 32 MB request limit. Try a shorter document "
            "or smaller agent/tick counts."
        ),
        "invalid_request_error": "The API rejected the request payload.",
    }
    hint = hints.get(err_type, "")
    hint_suffix = f" ({hint})" if hint else ""
    return f"Anthropic API error {status} {err_type}: {message}{hint_suffix}"


class AnthropicClient:
    """Calls Anthropic Messages API and parses JSON from the response text.

    Args:
        api_key: Anthropic API key.
        model: Model identifier (e.g. "claude-haiku-4-5-20251001").
        http_client: Optional custom httpx client (used by tests).
        max_tokens: Output token cap per call. Grounding and decision summary
            need headroom — 4096 is a safe default for Haiku.
        rpm: Requests per minute limit. 0 = unlimited. Prevents 429s at the
            source. Defaults conservatively to 40 to fit Anthropic's Tier 1
            Haiku limit of 50 RPM with a safety margin.
    """

    def __init__(
        self,
        api_key: str,
        model: str = ANTHROPIC_MODEL,
        http_client: httpx.AsyncClient | None = None,
        max_tokens: int = _MAX_TOKENS,
        rpm: int = 40,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._http = http_client or httpx.AsyncClient(timeout=120.0)
        self._rate_limiter = RateLimiter(rpm=rpm)

    async def generate(self, prompt: str, system: str | None = None, seed: int | None = None) -> dict:
        logger.info(
            "LLM call provider=anthropic model=%s prompt_chars=%d has_system=%s seed=%s",
            self.model, len(prompt), system is not None, seed,
        )
        if seed is not None:
            logger.debug("Anthropic does not support seed parameter — ignoring seed=%d", seed)
        logger.debug("LLM system:\n%s", system or "(none)")
        logger.debug("LLM prompt:\n%s", prompt)

        payload: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }

        raw = ""
        stop_reason: str | None = None
        for attempt in range(_MAX_RETRIES):
            # Throttle before sending — prevents 429s instead of reacting to them
            await self._rate_limiter.acquire()

            t0 = time.perf_counter()
            try:
                response = await self._http.post(_API_URL, json=payload, headers=headers)
            except httpx.ConnectError as exc:
                raise ConnectionError(
                    f"Cannot connect to Anthropic API at api.anthropic.com: {exc}"
                ) from exc
            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
                # Timeouts are transient — retry with backoff
                wait = min(2 ** attempt, 60)
                logger.warning(
                    "Anthropic request timed out (%s) — waiting %.1fs (attempt %d/%d)",
                    type(exc).__name__, wait, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(wait)
                continue
            except httpx.NetworkError as exc:
                # Transient network-layer error — retry once with backoff
                wait = min(2 ** attempt, 60)
                logger.warning(
                    "Anthropic network error (%s: %s) — waiting %.1fs (attempt %d/%d)",
                    type(exc).__name__, exc, wait, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(wait)
                continue

            # Retryable HTTP statuses: rate limit, transient server errors, overloaded
            if response.status_code in _RETRYABLE_STATUSES:
                if response.status_code == 429:
                    retry_after = response.headers.get("retry-after")
                    if retry_after:
                        try:
                            wait = float(retry_after)
                        except ValueError:
                            wait = min(2 ** attempt, 60)
                    else:
                        wait = min(2 ** attempt, 60)
                    logger.warning(
                        "Rate limited (429) provider=anthropic — waiting %.1fs (attempt %d/%d)",
                        wait, attempt + 1, _MAX_RETRIES,
                    )
                else:
                    wait = min(2 ** attempt, 60)
                    err_type, msg = _parse_error_body(response)
                    logger.warning(
                        "Anthropic transient error %d %s: %s — waiting %.1fs (attempt %d/%d)",
                        response.status_code, err_type, msg,
                        wait, attempt + 1, _MAX_RETRIES,
                    )
                await asyncio.sleep(wait)
                continue

            # Non-retryable 4xx (400, 401, 402, 403, 404, 413) — surface clearly
            if response.status_code >= 400:
                err_type, msg = _parse_error_body(response)
                message = _format_terminal_error(response.status_code, err_type, msg, self.model)
                logger.error(message)
                raise AnthropicError(message)

            # Success
            body = response.json()
            raw = body["content"][0]["text"]
            stop_reason = body.get("stop_reason")
            latency_ms = round((time.perf_counter() - t0) * 1000)

            logger.info(
                "LLM response latency_ms=%d response_chars=%d stop_reason=%s",
                latency_ms, len(raw), stop_reason,
            )
            logger.debug("LLM raw response:\n%s", raw)
            break
        else:
            raise AnthropicError(
                f"Exceeded {_MAX_RETRIES} retries on anthropic (model={self.model}). "
                "The API is rate-limited or overloaded. Reduce ANTHROPIC_RPM, use a "
                "higher tier, or try again later."
            )

        if stop_reason == "max_tokens":
            logger.warning(
                "Anthropic response hit max_tokens=%d — JSON likely truncated model=%s",
                self.max_tokens, self.model,
            )

        # Happy path — response is pure JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Fallback — extract the first balanced JSON object from surrounding prose
        candidate = _extract_balanced_json(raw)
        if candidate is None:
            logger.warning(
                "Anthropic response contained no balanced JSON object model=%s stop_reason=%s",
                self.model, stop_reason,
            )
            return {}

        try:
            parsed = json.loads(candidate)
            logger.warning("Anthropic response wrapped in prose — extracted JSON block")
            return parsed
        except json.JSONDecodeError as exc:
            logger.warning(
                "Anthropic JSON block failed to parse model=%s stop_reason=%s err=%s",
                self.model, stop_reason, exc,
            )
            return {}

    async def close(self) -> None:
        await self._http.aclose()
