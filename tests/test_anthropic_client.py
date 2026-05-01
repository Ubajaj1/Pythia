"""Tests for AnthropicClient JSON-parsing behavior."""

import json

import httpx
import pytest

from pythia.anthropic_client import AnthropicClient, _extract_balanced_json


def _mock_response(text: str, stop_reason: str = "end_turn") -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": text}],
                "stop_reason": stop_reason,
            },
        )
    return httpx.MockTransport(handler)


def _make_client(transport: httpx.MockTransport) -> AnthropicClient:
    return AnthropicClient(
        api_key="test-key",
        model="test-model",
        http_client=httpx.AsyncClient(transport=transport),
        rpm=0,  # disable rate limiting in tests
    )


class TestExtractBalancedJson:
    def test_returns_none_when_no_brace(self):
        assert _extract_balanced_json("no json here") is None

    def test_extracts_simple_object(self):
        assert _extract_balanced_json('{"a": 1}') == '{"a": 1}'

    def test_extracts_from_prose_prefix(self):
        raw = 'Sure! Here you go:\n{"facts": []}\nLet me know if you need more.'
        assert _extract_balanced_json(raw) == '{"facts": []}'

    def test_ignores_trailing_braces_in_prose(self):
        # The greedy regex bug would grab everything up to the last `}`
        raw = (
            '{"facts": [{"entity": "a", "fact": "b"}]}'
            "\n\nAdditional note: {inline braces in prose}"
        )
        extracted = _extract_balanced_json(raw)
        assert extracted == '{"facts": [{"entity": "a", "fact": "b"}]}'
        assert json.loads(extracted) == {"facts": [{"entity": "a", "fact": "b"}]}

    def test_handles_braces_inside_strings(self):
        raw = '{"text": "this has a } inside a string"}'
        extracted = _extract_balanced_json(raw)
        assert extracted == raw
        assert json.loads(extracted) == {"text": "this has a } inside a string"}

    def test_handles_escaped_quotes(self):
        raw = r'{"text": "she said \"hi\" and left"}'
        extracted = _extract_balanced_json(raw)
        assert extracted == raw
        assert json.loads(extracted) == {"text": 'she said "hi" and left'}

    def test_returns_none_when_truncated(self):
        # Unterminated object — no matching closing brace
        raw = '{"facts": [{"entity": "a", "fact":'
        assert _extract_balanced_json(raw) is None


class TestAnthropicClient:
    async def test_parses_pure_json_response(self):
        transport = _mock_response('{"stance": 0.5}')
        client = _make_client(transport)
        result = await client.generate("prompt")
        assert result == {"stance": 0.5}

    async def test_extracts_json_from_prose_wrapper(self):
        raw = 'Sure, here is the data:\n{"facts": [], "entity_summary": "x"}\nHope that helps!'
        transport = _mock_response(raw)
        client = _make_client(transport)
        result = await client.generate("prompt")
        assert result == {"facts": [], "entity_summary": "x"}

    async def test_does_not_splice_json_and_trailing_prose_braces(self):
        """Regression: greedy regex would slurp past the JSON into trailing braces."""
        raw = (
            '{"facts": [{"entity": "Netflix", "fact": "password sharing crackdown"}]}'
            "\n\nNote: the model may output {strange things} occasionally."
        )
        transport = _mock_response(raw)
        client = _make_client(transport)
        result = await client.generate("prompt")
        assert result == {
            "facts": [{"entity": "Netflix", "fact": "password sharing crackdown"}]
        }

    async def test_returns_empty_dict_when_response_truncated(self):
        """Simulate max_tokens truncation — JSON is incomplete."""
        raw = '{"facts": [{"entity": "a", "fact": "unterminated'
        transport = _mock_response(raw, stop_reason="max_tokens")
        client = _make_client(transport)
        result = await client.generate("prompt")
        assert result == {}

    async def test_returns_empty_dict_when_no_json_present(self):
        transport = _mock_response("I cannot help with that.")
        client = _make_client(transport)
        result = await client.generate("prompt")
        assert result == {}

    async def test_sends_configured_max_tokens(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "{}"}],
                    "stop_reason": "end_turn",
                },
            )

        transport = httpx.MockTransport(handler)
        client = AnthropicClient(
            api_key="test-key",
            model="test-model",
            http_client=httpx.AsyncClient(transport=transport),
            max_tokens=2048,
            rpm=0,
        )
        await client.generate("prompt", system="sys")
        assert captured["body"]["max_tokens"] == 2048
        assert captured["body"]["system"] == "sys"
        assert captured["body"]["messages"] == [{"role": "user", "content": "prompt"}]

    async def test_default_max_tokens_is_not_the_old_1024(self):
        """Guard against regressing the max_tokens default back to 1024."""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "{}"}],
                    "stop_reason": "end_turn",
                },
            )

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)
        await client.generate("prompt")
        assert captured["body"]["max_tokens"] >= 4096

    async def test_http_error_raises(self):
        """400 errors are terminal and raise AnthropicError."""
        from pythia.anthropic_client import AnthropicError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"type": "error", "error": {"type": "invalid_request_error", "message": "bad payload"}},
            )

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)
        with pytest.raises(AnthropicError, match="invalid_request_error"):
            await client.generate("prompt")


class TestAnthropicRateLimitHandling:
    """Verify the client retries on 429/529 and recovers automatically."""

    async def test_retries_on_429_then_succeeds(self, monkeypatch):
        # Patch asyncio.sleep so the retry backoff is instant in tests
        import asyncio
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    429,
                    json={"error": "rate_limited"},
                    headers={"retry-after": "2"},
                )
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": '{"ok": true}'}],
                    "stop_reason": "end_turn",
                },
            )

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)
        result = await client.generate("prompt")
        assert result == {"ok": True}
        assert call_count == 2
        # Verify we actually waited based on the Retry-After header
        assert 2.0 in sleeps

    async def test_retries_on_429_without_retry_after_uses_backoff(self, monkeypatch):
        import asyncio
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429, json={"error": "rate_limited"})
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "{}"}],
                    "stop_reason": "end_turn",
                },
            )

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)
        await client.generate("prompt")
        assert call_count == 2
        # First attempt uses 2**0 = 1 second backoff
        assert sleeps and sleeps[0] == 1.0

    async def test_retries_on_529_overload(self, monkeypatch):
        import asyncio
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(529, json={"error": "overloaded"})
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "{}"}],
                    "stop_reason": "end_turn",
                },
            )

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)
        await client.generate("prompt")
        assert call_count == 3

    async def test_raises_after_max_retries(self, monkeypatch):
        import asyncio

        async def fake_sleep(seconds: float) -> None:
            return None

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate_limited"})

        transport = httpx.MockTransport(handler)
        client = _make_client(transport)
        with pytest.raises(RuntimeError, match="Exceeded .* retries"):
            await client.generate("prompt")

    async def test_rate_limiter_throttles_concurrent_calls(self):
        """Verify the rate limiter instance is wired in and enforces spacing."""
        # Build a client with a strict RPM and check the limiter was created
        client = AnthropicClient(
            api_key="test-key",
            model="test-model",
            http_client=httpx.AsyncClient(transport=_mock_response("{}")),
            rpm=60,
        )
        assert client._rate_limiter.rpm == 60
        # 60 RPM = 1 second between tokens
        assert client._rate_limiter._interval == 1.0

    async def test_default_rpm_is_set(self):
        """Guard against regressing to no rate limiting."""
        client = AnthropicClient(
            api_key="test-key",
            model="test-model",
            http_client=httpx.AsyncClient(transport=_mock_response("{}")),
        )
        assert client._rate_limiter.rpm > 0


class TestAnthropicErrorHandling:
    """Verify terminal 4xx errors surface cleanly and transient 5xx errors retry."""

    async def _fake_sleep(self, monkeypatch):
        import asyncio

        async def no_sleep(seconds: float) -> None:
            return None

        monkeypatch.setattr(asyncio, "sleep", no_sleep)

    async def test_401_auth_error_is_terminal(self, monkeypatch):
        await self._fake_sleep(monkeypatch)
        from pythia.anthropic_client import AnthropicError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                json={"type": "error", "error": {"type": "authentication_error", "message": "invalid key"}},
            )

        client = _make_client(httpx.MockTransport(handler))
        with pytest.raises(AnthropicError, match="authentication_error"):
            await client.generate("prompt")

    async def test_404_not_found_mentions_model_name(self, monkeypatch):
        await self._fake_sleep(monkeypatch)
        from pythia.anthropic_client import AnthropicError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                404,
                json={"type": "error", "error": {"type": "not_found_error", "message": "model not found"}},
            )

        client = _make_client(httpx.MockTransport(handler))
        with pytest.raises(AnthropicError, match="test-model"):
            await client.generate("prompt")

    async def test_402_billing_error_is_terminal(self, monkeypatch):
        await self._fake_sleep(monkeypatch)
        from pythia.anthropic_client import AnthropicError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                402,
                json={"type": "error", "error": {"type": "billing_error", "message": "out of credits"}},
            )

        client = _make_client(httpx.MockTransport(handler))
        with pytest.raises(AnthropicError, match="billing_error"):
            await client.generate("prompt")

    async def test_413_request_too_large_is_terminal(self, monkeypatch):
        await self._fake_sleep(monkeypatch)
        from pythia.anthropic_client import AnthropicError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                413,
                json={"type": "error", "error": {"type": "request_too_large", "message": "too big"}},
            )

        client = _make_client(httpx.MockTransport(handler))
        with pytest.raises(AnthropicError, match="request_too_large"):
            await client.generate("prompt")

    async def test_500_api_error_retries_then_succeeds(self, monkeypatch):
        await self._fake_sleep(monkeypatch)

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(
                    500,
                    json={"type": "error", "error": {"type": "api_error", "message": "boom"}},
                )
            return httpx.Response(
                200,
                json={"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn"},
            )

        client = _make_client(httpx.MockTransport(handler))
        result = await client.generate("prompt")
        assert result == {}
        assert call_count == 3

    async def test_504_timeout_retries(self, monkeypatch):
        await self._fake_sleep(monkeypatch)

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    504,
                    json={"type": "error", "error": {"type": "timeout_error", "message": "timed out"}},
                )
            return httpx.Response(
                200,
                json={"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn"},
            )

        client = _make_client(httpx.MockTransport(handler))
        await client.generate("prompt")
        assert call_count == 2

    async def test_read_timeout_retries(self, monkeypatch):
        await self._fake_sleep(monkeypatch)

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ReadTimeout("network read timed out")
            return httpx.Response(
                200,
                json={"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn"},
            )

        client = _make_client(httpx.MockTransport(handler))
        await client.generate("prompt")
        assert call_count == 2

    async def test_connect_error_raises_connection_error(self, monkeypatch):
        await self._fake_sleep(monkeypatch)

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        client = _make_client(httpx.MockTransport(handler))
        with pytest.raises(ConnectionError, match="Cannot connect"):
            await client.generate("prompt")

    async def test_malformed_error_body_still_handled(self, monkeypatch):
        """Some edge cases return non-JSON error bodies — don't explode parsing."""
        await self._fake_sleep(monkeypatch)
        from pythia.anthropic_client import AnthropicError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, content=b"<html>Bad Request</html>")

        client = _make_client(httpx.MockTransport(handler))
        with pytest.raises(AnthropicError):
            await client.generate("prompt")
