# Responses API Cheat Sheet (Python + Azure OpenAI)

> All snippets below assume `deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]` and `client` is already initialized (see client setup).

## Basic request
```python
resp = client.responses.create(
    model=deployment,
    input="Hello",
    max_output_tokens=1000,
    store=False,
)
print(resp.output_text)
```

## Client setup — EntraID (recommended)
```python
import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default"
)

client = OpenAI(
    base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/v1/",
    api_key=token_provider,
)
```

## Client setup — API key
```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/v1/",
)
```

## Async client setup — EntraID
```python
import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncOpenAI

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default"
)

client = AsyncOpenAI(
    base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/v1/",
    api_key=token_provider,
)
```

## Async client setup — EntraID with explicit tenant (multi-tenant)

When the Azure OpenAI resource is in a **different tenant** than the default, pass `tenant_id` explicitly to the credential. This is common in dev/test scenarios where the developer's home tenant differs from the resource tenant.

```python
import os
from azure.identity.aio import (
    AzureDeveloperCliCredential,
    ChainedTokenCredential,
    ManagedIdentityCredential,
    get_bearer_token_provider,
)
from openai import AsyncOpenAI

# ManagedIdentityCredential for production (Azure Container Apps, App Service, etc.)
managed_identity_cred = ManagedIdentityCredential(
    client_id=os.getenv("AZURE_CLIENT_ID")  # user-assigned managed identity
)
# AzureDeveloperCliCredential for local dev — explicit tenant_id is critical
azd_cred = AzureDeveloperCliCredential(
    tenant_id=os.getenv("AZURE_TENANT_ID"),
    process_timeout=60,
)
# Chain: try managed identity first, fall back to azd CLI
azure_credential = ChainedTokenCredential(managed_identity_cred, azd_cred)

token_provider = get_bearer_token_provider(
    azure_credential, "https://cognitiveservices.azure.com/.default"
)

client = AsyncOpenAI(
    base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/v1/",
    api_key=token_provider,
)
```

## Async client migration — before/after

Before (deprecated):
```python
from openai import AsyncAzureOpenAI

client = AsyncAzureOpenAI(
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_ad_token_provider=token_provider,
)

resp = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=500,
)
print(resp.choices[0].message.content)
```

After:
```python
from openai import AsyncOpenAI

deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]

client = AsyncOpenAI(
    base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/v1/",
    api_key=token_provider,
)

resp = await client.responses.create(
    model=deployment,
    input="Hello",
    max_output_tokens=1000,
    store=False,
)
print(resp.output_text)
```

## Full sync migration — before/after

Before (legacy — Azure OpenAI Chat Completions):
```python
from openai import AzureOpenAI
import os

client = AzureOpenAI(
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)

resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=500,
)
print(resp.choices[0].message.content)
```

After (Responses API — Azure OpenAI v1 endpoint):
```python
from openai import OpenAI
import os

deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]

client = OpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    base_url=f"{os.environ['AZURE_OPENAI_ENDPOINT'].rstrip('/')}/openai/v1/",
)

resp = client.responses.create(
    model=deployment,
    input="Hello",
    max_output_tokens=1000,
    store=False,
)
print(resp.output_text)
```

## Streaming (sync)
```python
stream = client.responses.create(
    model=deployment,
    input="Explain streaming in simple terms",
    max_output_tokens=1000,
    stream=True,
)
for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
    elif event.type == "response.completed":
        print()  # newline at end
```

## Streaming (async)
```python
stream = await client.responses.create(
    model=deployment,
    input="Explain streaming in simple terms",
    max_output_tokens=1000,
    stream=True,
)
async for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
    elif event.type == "response.completed":
        print()
```

## Web app streaming — backend-to-frontend shape

When migrating a web app that streams SSE/JSONL to a frontend, the **backend serialization format** changes. Design the new backend output to preserve the frontend's existing access patterns so the frontend needs no changes.

**Before** — Chat Completions backend typically serialized each chunk's `choices[0]` dict:
```python
# Old: serialized full choice dict per chunk
async for chunk in response:
    if chunk.choices:
        yield json.dumps(chunk.choices[0].model_dump()) + "\n"
```
Frontend read: `response.delta.content` (deep path into the choice object).

**After** — Responses API backend emits a minimal shape preserving the same frontend access path:
```python
# New: emit only what the frontend needs
async for event in await chat_coroutine:
    if event.type == "response.output_text.delta":
        yield json.dumps({"delta": {"content": event.delta}}) + "\n"
    elif event.type == "response.completed":
        yield json.dumps({"delta": {"content": None}, "finish_reason": "stop"}) + "\n"
```
Frontend still reads `response.delta.content` — **no frontend changes needed**.

> **Key insight**: The Responses API streaming shape (`event.type` + `event.delta`) is fundamentally different from Chat Completions (`chunk.choices[0].delta.content`). But your backend-to-frontend contract is yours to define. Shape the backend output to match what the frontend already expects.

## Streaming event sequence

When `stream: true`, the API emits events in this order:
1. `response.created` – response object initialized
2. `response.in_progress` – generation started
3. `response.output_item.added` – output item created
4. `response.content_part.added` – content part started
5. `response.output_text.delta` – text chunks (multiple, each has `delta: string`)
6. `response.output_text.done` – text generation finished
7. `response.content_part.done` – content part finished
8. `response.output_item.done` – output item finished
9. `response.completed` – full response complete

For basic text streaming, only handle `response.output_text.delta` (for text chunks) and `response.completed` (for finish).

## Streaming error handling in web apps

When streaming in a web app, wrap the async iteration in `try/except` and yield errors as JSON so the frontend can display them gracefully (e.g., rate limits, transient failures):

```python
@stream_with_context
async def response_stream():
    chat_coroutine = client.responses.create(
        model=deployment,
        input=all_messages,
        max_output_tokens=1000,
        stream=True,
        store=False,
    )
    try:
        async for event in await chat_coroutine:
            if event.type == "response.output_text.delta":
                yield json.dumps({"delta": {"content": event.delta}}) + "\n"
            elif event.type == "response.completed":
                yield json.dumps({"delta": {"content": None}, "finish_reason": "stop"}) + "\n"
    except Exception as e:
        current_app.logger.error(e)
        yield json.dumps({"error": str(e)}) + "\n"
```

> **Why this matters**: Azure OpenAI returns `429 Too Many Requests` during rate limiting. Without the `try/except`, the streaming response silently dies. With it, the frontend receives `{"error": "Too Many Requests"}` and can show a retry prompt.

## Streaming event types (Python SDK)

- `ResponseTextDeltaEvent`: `type='response.output_text.delta'`, `delta: str`
- `ResponseCompletedEvent`: `type='response.completed'`, `response: Response`

## Conversation format
```python
# The Responses API supports conversation format via input array
response = client.responses.create(
    model=deployment,
    input=[
        {"role": "system", "content": "You are an Azure cloud architect."},
        {"role": "user", "content": "Design a scalable web application architecture."},
    ],
    max_output_tokens=1000,
)
print(response.output_text)
```

## Multi-turn conversation
```python
# Build a conversation with Responses API
messages = [
    {"role": "system", "content": "You are a helpful coding assistant."},
    {"role": "user", "content": "Write a Python function to calculate factorial"},
]

response = client.responses.create(
    model=deployment,
    input=messages,
    max_output_tokens=400,
)

# Add assistant's response to conversation
messages.append({"role": "assistant", "content": response.output_text})

# Continue the conversation
messages.append({"role": "user", "content": "Now optimize it with memoization"})

response2 = client.responses.create(
    model=deployment,
    input=messages,
    max_output_tokens=400,
)
print(response2.output_text)
```

Content-typed multi-turn (explicit `input_text`/`output_text`):
```python
messages = [
    {"role": "system", "content": [{"type": "input_text", "text": "You are helpful."}]},
    {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]},
    {"role": "assistant", "content": [{"type": "output_text", "text": "Hello!"}]},
    {"role": "user", "content": [{"type": "input_text", "text": "Tell me a joke"}]},
]
resp = client.responses.create(model=deployment, input=messages, store=False)
```

## Accessing reasoning tokens
```python
# Reasoning models use internal reasoning — you can see how many reasoning tokens were used
response = client.responses.create(
    model=deployment,
    input="Explain quantum computing in simple terms",
    max_output_tokens=1000,
)
print(response.output_text)
print(f"Status: {response.status}")
print(f"Reasoning tokens: {response.usage.output_tokens_details.reasoning_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")
```

> **Important**: Use `max_output_tokens=1000` (not 50–200) to account for reasoning models' internal reasoning process. The model uses reasoning tokens internally before generating the final output.

## Structured output — JSON Schema
```python
resp = client.responses.create(
    model=deployment,
    input="What is the capital of France?",
    max_output_tokens=500,
    text={
        "format": {
            "type": "json_schema",
            "name": "Output",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
        }
    },
    store=False,
)
import json
data = json.loads(resp.output_text)
print(data["answer"])
```

## Tool use

- Define functions in `tools` with JSON Schema params; let the model decide with `tool_choice="auto"` or force a specific tool.
- When the model asks to call a tool, execute it in your app and include the tool result in the next request as a `tool` role item within `input`.
- Keep schemas minimal; validate inputs before execution.

```python
# Built-in web search example
resp = client.responses.create(
    model=deployment,
    tools=[{"type": "web_search_preview"}],
    input="What was a positive news story from today?",
    store=False,
)
print(resp.output_text)
```

## Image input
```python
resp = client.responses.create(
    model=deployment,
    input=[
        {"role": "user", "content": "What two teams are playing?"},
        {"role": "user", "content": [{"type": "input_image", "image_url": "https://example.com/image.jpg"}]},
    ],
    max_output_tokens=500,
    store=False,
)
print(resp.output_text)
```
