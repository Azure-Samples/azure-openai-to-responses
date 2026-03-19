"""
Test harness for Azure OpenAI Responses API migration.

Validates that a migrated codebase correctly calls the Responses API
against a live Azure OpenAI deployment. Covers: basic completion,
streaming, async, structured output, multi-turn, and tool use.

Prerequisites:
    pip install openai azure-identity pytest pytest-asyncio

Environment variables:
    AZURE_OPENAI_ENDPOINT    - Your Azure OpenAI resource endpoint
    AZURE_OPENAI_DEPLOYMENT  - Deployment name (e.g. gpt-5-mini)
    AZURE_OPENAI_API_KEY     - API key (if not using EntraID)

Usage:
    pytest test_migration.py -v
"""

import json
import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")

skip_reason = ""
if not ENDPOINT:
    skip_reason = "AZURE_OPENAI_ENDPOINT not set"
elif not DEPLOYMENT:
    skip_reason = "AZURE_OPENAI_DEPLOYMENT not set"
elif not API_KEY:
    skip_reason = "AZURE_OPENAI_API_KEY not set (EntraID variant not wired in this harness)"

pytestmark = pytest.mark.skipif(bool(skip_reason), reason=skip_reason or "n/a")


def _make_sync_client():
    from openai import OpenAI

    return OpenAI(
        api_key=API_KEY,
        base_url=f"{ENDPOINT.rstrip('/')}/openai/v1/",
    )


def _make_async_client():
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=API_KEY,
        base_url=f"{ENDPOINT.rstrip('/')}/openai/v1/",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBasicCompletion:
    """Non-streaming responses.create returns non-empty output_text."""

    def test_basic_request(self):
        client = _make_sync_client()
        resp = client.responses.create(
            model=DEPLOYMENT,
            input="Say hello in exactly one word.",
            max_output_tokens=50,
            store=False,
        )
        assert resp.output_text, "output_text must not be empty"
        assert resp.status == "completed"

    def test_conversation_format(self):
        client = _make_sync_client()
        resp = client.responses.create(
            model=DEPLOYMENT,
            input=[
                {"role": "system", "content": "Reply in one word."},
                {"role": "user", "content": "What color is the sky?"},
            ],
            max_output_tokens=50,
            store=False,
        )
        assert resp.output_text


class TestStreaming:
    """Streaming yields delta events and completes."""

    def test_sync_streaming(self):
        client = _make_sync_client()
        stream = client.responses.create(
            model=DEPLOYMENT,
            input="Count from 1 to 5.",
            max_output_tokens=100,
            stream=True,
            store=False,
        )
        deltas = []
        completed = False
        for event in stream:
            if event.type == "response.output_text.delta":
                deltas.append(event.delta)
            elif event.type == "response.completed":
                completed = True
        assert deltas, "Must receive at least one delta event"
        assert completed, "Must receive response.completed event"

    @pytest.mark.asyncio
    async def test_async_streaming(self):
        client = _make_async_client()
        stream = await client.responses.create(
            model=DEPLOYMENT,
            input="Count from 1 to 5.",
            max_output_tokens=100,
            stream=True,
            store=False,
        )
        deltas = []
        completed = False
        async for event in stream:
            if event.type == "response.output_text.delta":
                deltas.append(event.delta)
            elif event.type == "response.completed":
                completed = True
        assert deltas, "Must receive at least one delta event"
        assert completed, "Must receive response.completed event"


class TestAsyncBasic:
    """AsyncOpenAI non-streaming works."""

    @pytest.mark.asyncio
    async def test_async_basic(self):
        client = _make_async_client()
        resp = await client.responses.create(
            model=DEPLOYMENT,
            input="Say hello.",
            max_output_tokens=50,
            store=False,
        )
        assert resp.output_text


class TestStructuredOutput:
    """text.format with json_schema produces parseable JSON matching the schema."""

    def test_json_schema(self):
        client = _make_sync_client()
        resp = client.responses.create(
            model=DEPLOYMENT,
            input="What is the capital of France?",
            max_output_tokens=200,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "CapitalAnswer",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "country": {"type": "string"},
                            "capital": {"type": "string"},
                        },
                        "required": ["country", "capital"],
                        "additionalProperties": False,
                    },
                }
            },
            store=False,
        )
        data = json.loads(resp.output_text)
        assert "capital" in data, f"Missing 'capital' key in {data}"
        assert "country" in data, f"Missing 'country' key in {data}"


class TestMultiTurn:
    """Multi-turn conversation produces coherent follow-up."""

    def test_multi_turn(self):
        client = _make_sync_client()
        messages = [
            {"role": "system", "content": "You are a math tutor. Be concise."},
            {"role": "user", "content": "What is 2+2?"},
        ]
        resp1 = client.responses.create(
            model=DEPLOYMENT,
            input=messages,
            max_output_tokens=50,
            store=False,
        )
        assert resp1.output_text

        messages.append({"role": "assistant", "content": resp1.output_text})
        messages.append({"role": "user", "content": "Now multiply that by 3."})

        resp2 = client.responses.create(
            model=DEPLOYMENT,
            input=messages,
            max_output_tokens=50,
            store=False,
        )
        assert resp2.output_text


class TestToolUse:
    """Built-in web_search_preview tool returns output_text."""

    def test_web_search(self):
        client = _make_sync_client()
        resp = client.responses.create(
            model=DEPLOYMENT,
            tools=[{"type": "web_search_preview"}],
            input="What is today's date?",
            max_output_tokens=200,
            store=False,
        )
        assert resp.output_text


class TestNoLegacyShapes:
    """Sanity check: responses don't expose legacy Chat Completions attributes."""

    def test_no_choices_attribute(self):
        client = _make_sync_client()
        resp = client.responses.create(
            model=DEPLOYMENT,
            input="Hello",
            max_output_tokens=50,
            store=False,
        )
        assert not hasattr(resp, "choices"), "Response must not have 'choices' (legacy shape)"
        assert hasattr(resp, "output_text"), "Response must have 'output_text'"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
