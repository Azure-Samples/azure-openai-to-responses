# Demo: Migrated Chat App (Responses API)

This is [Azure-Samples/openai-chat-app-quickstart](https://github.com/Azure-Samples/openai-chat-app-quickstart) **after migration** from Chat Completions to the Responses API. It shows what a real migrated app looks like.

## What changed

| File | Migration change |
|---|---|
| `src/quartapp/chat.py` | `AsyncAzureOpenAI` → `AsyncOpenAI(base_url=...)`, `chat.completions.create` → `responses.create`, streaming rewritten |
| `tests/conftest.py` | `ChatCompletionChunk` mocks → `MockResponseEvent` / `AsyncResponseIterator` |
| `tests/test_app.py` | Assertions updated to `isinstance(client, AsyncOpenAI)` |
| `tests/snapshots/` | `choices[0].delta.content` → `{"delta": {"content": "..."}}` |
| `infra/aca.bicep` | Removed `AZURE_OPENAI_API_VERSION`; uses `AZURE_CLIENT_ID` |
| `.env.sample` | Removed `AZURE_OPENAI_API_VERSION` |

## Key files to study

- **`src/quartapp/chat.py`** — The main backend code. Shows async client setup with `ChainedTokenCredential`, `responses.create` with streaming, and backend-to-frontend event shaping.
- **`tests/conftest.py`** — How to mock Responses API streaming in pytest.
- **`tests/test_app.py`** — Updated assertions for the new client and response shapes.

## Running tests

```bash
cd demo/openai-chat-app-quickstart
pip install -e src
pip install pytest pytest-asyncio
pytest tests/ -v
```

## Original repo

See the [original Azure Samples repo](https://github.com/Azure-Samples/openai-chat-app-quickstart) for deployment instructions, Codespaces setup, and full infrastructure.
