# Troubleshooting, Risk Table & Gotchas

## Troubleshooting 400s

| Error | Fix |
|-------|-----|
| `missing_required_parameter: text.format.name` | Add `"name"` key to the format dict (e.g., `"name": "Output"`) |
| `invalid_type: text.format` | Ensure `text.format` is a dict with `type`, `name`, `strict`, `schema` keys — not a string |
| `invalid input content type` | Use `input_text`/`output_text` content types instead of Chat `text` |
| `integer below minimum value` for `max_output_tokens` | Minimum is **16** on Azure OpenAI. Use 50+ for tests, 1000+ for production. |
| `429 Too Many Requests` during streaming | Rate limited. Wrap streaming in `try/except`, yield error JSON to frontend, implement backoff/retry. |

---

## Migration Risk Table

| Symptom | Likely Mistake | Fix |
|---------|---------------|-----|
| Empty `output_text` / truncated response | `max_output_tokens` too low for reasoning models | Set `max_output_tokens=1000` or higher — reasoning tokens count against the limit |
| `400 invalid_type: text.format` | Passed `response_format` string instead of `text.format` dict | Use `text={"format": {"type": "json_schema", "name": "...", "strict": True, "schema": {...}}}` |
| `404 Not Found` on `/openai/v1/responses` | Wrong `base_url` — missing `/openai/v1/` suffix | Ensure `base_url=f"{endpoint}/openai/v1/"` (with trailing slash) |
| `401 Unauthorized` after switching to `OpenAI()` | `api_key` not set or token provider not passed correctly | For EntraID: `api_key=token_provider` (the callable). For API key: `api_key=os.environ["AZURE_OPENAI_API_KEY"]` |
| Model returns `deployment not found` | `model` param doesn't match your Azure deployment name | Use `model=os.environ["AZURE_OPENAI_DEPLOYMENT"]` — this is the deployment name, not the model name |
| `json.loads(resp.output_text)` raises `JSONDecodeError` | Schema not enforced or model doesn't support strict JSON | Ensure `"strict": True` in schema, and verify model supports structured output |
| Streaming yields no `delta` events | Checking wrong event type | Filter on `event.type == "response.output_text.delta"`, not Chat's `chat.completion.chunk` |
| Tool calls loop infinitely | Missing tool result in follow-up `input` | After executing a tool, append a `{"role": "tool", ...}` item to `input` in the next request |
| `temperature` error with GPT-5 | Explicit `temperature` value other than 1 | Remove `temperature` or set to `1` for GPT-5 models |
| `400 integer_below_min_value` for `max_output_tokens` | Value below 16 | Azure OpenAI enforces `max_output_tokens >= 16`. Use 50+ for smoke tests, 1000+ for production. |
| `429 Too Many Requests` mid-stream | Rate limited by Azure OpenAI | Stream breaks silently without error handling. Always wrap `async for event in await coroutine:` in `try/except` and yield `{"error": str(e)}` to the frontend. |
| `AzureDeveloperCliCredential` → `CredentialUnavailableError` | Wrong tenant or not logged in | Pass `tenant_id=os.getenv("AZURE_TENANT_ID")` explicitly. Run `azd auth login --tenant <tenant-id>` locally. |

---

## Gotchas

1. If you previously used Chat Completions for conversation state, manage your own state explicitly with Responses.
2. Prefer `max_output_tokens` over legacy `max_tokens`.
3. When migrating to `gpt-5`, ensure `temperature` is not specified or is set to `1`.
4. Replace Chat `content[].type: "text"` with Responses `content[].type: "input_text"` for user/system inputs.
5. For `text.format`, supply a proper dict (e.g., `{"type": "json_schema", "name": "Output", "schema": ..., "strict": True}`), not a plain string.
6. The `seed` parameter is not supported in Responses; remove it from requests.
7. **Reasoning**: Only include `reasoning` if the original code already used it. Do not add `reasoning` to API calls that didn't have it — many models (e.g., gpt-4o-mini) don't support this parameter.
8. **`max_output_tokens` sizing**: For reasoning models (GPT-5-mini, GPT-5), use `max_output_tokens=1000` or higher — not 50–200. The model uses reasoning tokens internally before generating visible output; too-low limits cause truncated or empty responses.
9. **`_azure_ad_token_provider` is gone**: `AsyncOpenAI` / `OpenAI` have no `_azure_ad_token_provider` attribute. Tests or code that access this attribute will fail with `AttributeError`. The token provider is passed as `api_key` and is not inspectable on the client object.
10. **Snapshot / golden files**: If the test suite uses snapshot testing, **all** snapshot files containing Chat Completions streaming shapes (`choices[0]`, `content_filter_results`, `function_call`, etc.) must be updated to the new Responses shape. This is easy to miss and causes snapshot assertion failures.
11. **Mock monkeypatch path**: The monkeypatch target changes from `openai.resources.chat.AsyncCompletions.create` → `openai.resources.responses.AsyncResponses.create` (or `Responses.create` for sync). Using the old path silently does nothing — the mock won't intercept, and tests hit the real API or fail.
12. **`input` not `messages`**: Mock functions must read `kwargs.get("input")` not `kwargs.get("messages")`. The Responses API uses `input` for conversation history.
13. **Env var naming**: Azure Identity SDK uses `AZURE_CLIENT_ID` (not `AZURE_OPENAI_CLIENT_ID`) for `ManagedIdentityCredential(client_id=...)`. Rename in tests, `.env` files, app settings, and Bicep/infra.
14. **`max_output_tokens` minimum is 16**: Azure OpenAI rejects values below 16 with `400 integer_below_min_value`. Use `50` for smoke tests, `1000`+ for production. The old `max_tokens` had no such minimum.
15. **`tenant_id` for `AzureDeveloperCliCredential`**: When the Azure OpenAI resource is in a different tenant, you **must** pass `tenant_id` explicitly — `AzureDeveloperCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID"))`. Without it, the credential silently uses the wrong tenant and returns `401`.
16. **Rate limits surface differently in streaming**: With Chat Completions, a 429 typically prevented the stream from starting. With Responses API streaming, a 429 can occur **mid-stream** — the async iterator raises an exception. Always wrap the streaming loop in `try/except` and yield an error JSON line so the frontend can handle it gracefully.
17. **Streaming error handling is mandatory for web apps**: The pattern `try: async for event in await coroutine: ... except Exception as e: yield json.dumps({"error": str(e)})` is critical. Without it, the SSE/JSONL stream silently dies on any server-side error and the frontend hangs.
