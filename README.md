# Azure OpenAI To Responses

Migrate your Python apps from the **AzureOpenAI client with Chat Completions API** to the **OpenAI client with Responses API**.

> **GPT-5 and newer models require the Responses API.** Migrating now future-proofs your apps and unlocks deep tool integration, structured output, and a stable `/openai/v1/` endpoint with no `api_version` management.

This skill follows the open [Agent Skills](https://agentskills.io/) format — install it in one command and use it from [GitHub Copilot](https://github.com/features/copilot), [OpenAI Codex](https://developers.openai.com/codex), [Claude Code](https://claude.ai/code), and [many more](#agent-skills-compatibility).

### What changes?

| Before (Chat Completions) | After (Responses API) |
|---|---|
| `AzureOpenAI()` / `AsyncAzureOpenAI()` | `OpenAI(base_url=...)` / `AsyncOpenAI(base_url=...)` |
| `client.chat.completions.create(messages=...)` | `client.responses.create(input=...)` |
| `resp.choices[0].message.content` | `resp.output_text` |
| `api_version="2024-12-01-preview"` | Not needed — `/openai/v1/` is stable |

---

## Get started

### 1. Install the skill

```bash
npx skills add Azure-Samples/azure-openai-to-responses
```

### 2. Ask your agent to migrate

In any [compatible agent](#agent-skills-compatibility) (VS Code Copilot, Claude Code, Cursor, Gemini CLI, etc.):

> *Migrate my app from Chat Completions to the Responses API*

The skill activates automatically. The agent will scan your code, plan the edits, migrate each file, and verify with the scanner and your tests.

### 3. Verify

The agent runs verification automatically, but you can double-check:

```bash
# Scanner should report zero hits
python migrate.py scan /path/to/your-app

# Run your repo's own tests
cd /path/to/your-app && pytest
```

### Demo: what a migrated app looks like

The [`demo/openai-chat-app-quickstart/`](demo/openai-chat-app-quickstart/) directory is a fully migrated [Azure Samples chat app](https://github.com/Azure-Samples/openai-chat-app-quickstart) — a real Quart (async Flask) app.

| File | What changed |
|---|---|
| `src/quartapp/chat.py` | `AsyncAzureOpenAI` → `AsyncOpenAI`, `chat.completions.create` → `responses.create`, streaming rewritten |
| `tests/conftest.py` | `ChatCompletionChunk` mocks → `MockResponseEvent` / `AsyncResponseIterator` |
| `tests/test_app.py` | Assertions updated to `isinstance(client, AsyncOpenAI)` |
| `tests/snapshots/` | `choices[0].delta.content` → `{"delta": {"content": "..."}}` |
| `infra/*.bicep`, `.env.sample` | Removed `AZURE_OPENAI_API_VERSION` / `openAiApiVersion`; added `AZURE_CLIENT_ID` |

---

## Agent Skills compatibility

This skill follows the open [Agent Skills](https://agentskills.io/) format. Install it once and use it from any compatible AI coding agent.

### Supported agents

| Agent | Status |
|---|---|
| [GitHub Copilot](https://github.com/features/copilot) | ✅ Skill + custom agent |
| [OpenAI Codex](https://developers.openai.com/codex) | ✅ |
| [Claude Code](https://claude.ai/code) | ✅ |
| [Cursor](https://cursor.com/) | ✅ |
| [Gemini CLI](https://geminicli.com/) | ✅ |
| [Amp](https://ampcode.com/) | ✅ |
| [Goose](https://block.github.io/goose/) | ✅ |
| [Junie](https://junie.jetbrains.com/) (JetBrains) | ✅ |
| [Qodo](https://www.qodo.ai/) | ✅ |
| [Letta](https://www.letta.com/) | ✅ |

See the [Agent Skills spec](https://agentskills.io/specification) and [VS Code skill authoring docs](https://code.visualstudio.com/docs/copilot/customization/agent-skills#_create-a-skill) for details.

---

## Advanced manual migration

For air-gapped environments, custom LLM pipelines, org-wide bulk workflows, standalone tooling, or when you want full manual control.

<details>
<summary><strong>Expand for setup, single-repo, bulk, and scanner details</strong></summary>

### Setup

```bash
git clone https://github.com/YOUR_ORG/azure-openai-to-responses.git
cd azure-openai-to-responses
pip install -e ".[dev]"
```

### Single-repo migration (manual)

#### Step 1 — Scan for legacy patterns

```bash
python migrate.py scan /path/to/your-app
```

The scanner finds every call site that needs to change, grouped by category: client constructors, API calls, response shapes, parameters, env vars, and test infrastructure.

#### Step 2 — Migrate with an agent or manually

**With VS Code Copilot agent:** Open your app as a [multi-root workspace](https://code.visualstudio.com/docs/editor/multi-root-workspaces) with this repo, then:

```
@azure-openai-to-responses migrate the app at /path/to/your-app
```

**With any LLM:** Feed [SKILL.md](skills/azure-openai-to-responses/SKILL.md) as context and ask it to migrate your code. The [cheat sheet](skills/azure-openai-to-responses/references/cheat-sheet.md) has copy-paste code for every pattern.

**Fully manual:** Follow [SKILL.md](skills/azure-openai-to-responses/SKILL.md) step by step using the [cheat sheet](skills/azure-openai-to-responses/references/cheat-sheet.md), [test migration guide](skills/azure-openai-to-responses/references/test-migration.md), and [troubleshooting guide](skills/azure-openai-to-responses/references/troubleshooting.md).

#### Step 3 — Verify

```bash
python migrate.py scan /path/to/your-app   # zero hits
cd /path/to/your-app && pytest              # all tests pass
```

### Bulk migration across repos

Roll out the migration across your entire GitHub org with a single workflow that discovers, clones, tracks, and sends PRs. Requires the [`gh` CLI](https://cli.github.com/).

```bash
# Discover + clone + scan
python migrate.py bulk prepare --org YOUR_ORG

# Migrate each repo (agent, LLM, or manual)
# ...

# Review status
python migrate.py bulk status --workdir ./migrations

# Send PRs (interactive: all / selective / one-by-one)
python migrate.py bulk send-prs --workdir ./migrations
```

### Scanner standalone

The scanner works independently — no agent or LLM needed:

```bash
python migrate.py scan /path/to/your-app
python skills/azure-openai-to-responses/scripts/detect_legacy.py /path/to/your-app
```

</details>

---

## Model compatibility

> **❗ Important:** Check that your deployed model supports the Responses API before migrating — run `python migrate.py models --subscription YOUR_SUB_ID --location YOUR_REGION` or see the table below. Older models like `gpt-4o` support Responses but **not all features** (see [known limitations](#known-limitations-with-older-models)).

### Responses API support matrix (eastus2, March 2026)

| Model | Version | Responses | Chat | JSON Schema | Agents | Fine-tune |
|---|---|:---:|:---:|:---:|:---:|:---:|
| gpt-4 | 0613 | Y | Y | - | Y | - |
| gpt-4-32k | 0613 | Y | Y | - | Y | - |
| gpt-4o | 2024-05-13 | Y | Y | Y | Y | - |
| gpt-4o | 2024-08-06 | Y | Y | Y | Y | Y |
| gpt-4o | 2024-11-20 | Y | Y | Y | Y | - |
| gpt-4o-mini | 2024-07-18 | Y | Y | Y | Y | Y |
| gpt-4.1 | 2025-04-14 | Y | Y | - | Y | Y |
| gpt-4.1-mini | 2025-04-14 | Y | Y | - | Y | Y |
| gpt-4.1-nano | 2025-04-14 | Y | Y | - | Y | Y |
| o1 | 2024-12-17 | Y | Y | - | Y | - |
| o3-mini | 2025-01-31 | Y | Y | - | Y | - |
| o4-mini | 2025-04-16 | Y | Y | - | Y | Y |
| gpt-5 | 2025-08-07 | Y | Y | - | Y | - |
| gpt-5-mini | 2025-08-07 | Y | Y | - | Y | - |
| gpt-5-nano | 2025-08-07 | Y | Y | - | Y | - |
| gpt-5-chat | 2025-10-03 | Y | Y | - | Y | - |
| gpt-5-codex | 2025-09-15 | Y | - | - | Y | - |
| gpt-5-pro | 2025-10-06 | Y | - | - | Y | - |
| gpt-5.1 | 2025-11-13 | Y | Y | - | - | - |
| gpt-5.1-chat | 2025-11-13 | Y | Y | - | - | - |
| gpt-5.1-codex | 2025-11-13 | Y | - | - | Y | - |
| gpt-5.1-codex-mini | 2025-11-13 | Y | - | - | Y | - |
| gpt-5.1-codex-max | 2025-12-04 | Y | - | - | Y | - |
| gpt-5.2-chat | 2026-02-10 | Y | Y | - | Y | - |
| gpt-5.3-chat | 2026-03-03 | Y | Y | - | Y | - |
| codex-mini | 2025-05-16 | Y | - | - | Y | - |

> **Y** = supported, **-** = not declared. JSON Schema column combines `jsonSchemaResponse` and `jsonObjectResponse` flags. Availability varies by region — run `python migrate.py models` for your region's live data.

### Check your region

```bash
python migrate.py models --subscription YOUR_SUB_ID --location eastus2
python migrate.py models --subscription YOUR_SUB_ID --location eastus2 --filter gpt-4o,gpt-5
python migrate.py models --subscription YOUR_SUB_ID --location eastus2 --all   # includes non-Responses models
python migrate.py models --subscription YOUR_SUB_ID --location eastus2 --json  # for scripting
```

### Known limitations with older models

> **⚠️ WARNING:** Older models (e.g., `gpt-4o`, `gpt-4`) support the Responses API but **do not support all features fully**. The migration still works for basic text, chat, streaming, and tools — but test thoroughly.

| Limitation | Details |
|---|---|
| `reasoning` parameter | Not supported on `gpt-4o-mini`, `gpt-4o`, and many non-reasoning models. Only migrate `reasoning` if it was already present in the original code. |
| `seed` parameter | Not supported in Responses API at all — remove from all requests. |
| Structured output (`text.format`) | Older models may not enforce `strict: true` JSON schemas reliably. |
| Tool orchestration | GPT-5+ orchestrates tool calls as part of internal reasoning. Older models on Responses still work but lack this deep integration. |
| Temperature constraints | When migrating to `gpt-5` or o-series, temperature must be omitted or set to `1`. |
| `max_output_tokens` | Minimum is **16** on Azure OpenAI. Values below 16 return a 400 error. |
| **O-series models** | `o1`, `o3-mini`, `o3`, `o4-mini` have specific constraints: `temperature` must be `1`, `top_p` not supported, `max_completion_tokens` must be migrated to `max_output_tokens` (set to 4096+), `reasoning_effort` migrates to `reasoning={"effort": "..."}`. See the [cheat sheet](skills/azure-openai-to-responses/references/cheat-sheet.md#o-series-reasoning-models-o1-o3-mini-o3-o4-mini). |
| **GitHub Models** | `models.github.ai` and `models.inference.ai.azure.com` **do not support the Responses API**. Remove GitHub Models code paths during migration and switch to Azure OpenAI, OpenAI, or a compatible local endpoint. |
| **Frameworks** | **Microsoft Agent Framework (MAF)**: In MAF 1.0.0+, `OpenAIChatClient` already uses the Responses API — no migration needed. Replace `OpenAIChatCompletionClient` with `OpenAIChatClient` if present. For pre-1.0.0, upgrade to `agent-framework-openai>=1.0.0`. **LangChain**: add `use_responses_api=True` to `ChatOpenAI()` and change `.content` → `.text` on response messages. See the [cheat sheet](skills/azure-openai-to-responses/references/cheat-sheet.md#microsoft-agent-framework-maf-migration) for before/after examples. |

**Recommendation:** If staying on an older model (gpt-4o, gpt-4), the migration to Responses API works for core functionality. For full benefit (especially tool orchestration and reasoning), upgrade to gpt-5.1 or gpt-5.2 — both have broad cross-region availability.

---

## Frontend migration guidance

**The Responses API is a server-side concern.** In most cases, you should only migrate your Python backend — the HTTP contract between your frontend and backend should stay unchanged.

| Scenario | Recommendation |
|---|---|
| **Frontend calls your backend API** (typical) | Migrate the backend only. Your frontend sends messages via your API; the backend translates to/from the Responses API. The frontend doesn't need to know which OpenAI API shape the backend uses. |
| **Backend is a thin pass-through** | Consider adopting the Responses request/response shape in your backend's HTTP interface to eliminate a translation layer. This means your frontend would send `input` instead of `messages` and receive `output_text` instead of `choices[0].message.content`. |
| **Frontend calls OpenAI directly** (client-side API key) | **Move those calls to a backend first.** Client-side API keys are a security risk. Once the calls are server-side, migrate normally. |
| **Frontend uses SSE/streaming** | The streaming event shape changes (no more `choices[0].delta`). If your frontend parses raw SSE events from a pass-through backend, update it to handle `response.output_text.delta` events. If your backend already re-formats events before sending, no frontend change is needed. |

> **Bottom line:** For most apps, migrate the backend and leave the frontend alone. Only touch the frontend if it directly consumes OpenAI's wire format.

---

## References

- [Azure OpenAI Starter Kit](https://aka.ms/openai/start) — quickstart examples, model compatibility, and Responses API guidance
- [Azure OpenAI Responses API docs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses)
- [OpenAI Responses API reference](https://platform.openai.com/docs/api-reference/responses)

<details>
<summary>CLI reference</summary>

| Command | Description |
|---|---|
| `python migrate.py scan <dirs>` | Scan directories for legacy patterns. Exit 0 = clean, exit 1 = migration needed. |
| `python migrate.py org-scan --org <name>` | Search a GitHub org for repos using legacy patterns (via `gh` CLI). |
| `python migrate.py org-scan --org <name> --json` | Same, but JSON output for scripting. |
| `python migrate.py bulk prepare --org <name>` | Clone flagged repos, create branches, scan, produce report. |
| `python migrate.py bulk status --workdir <dir>` | Show migration status + files changed per repo. |
| `python migrate.py bulk send-prs --workdir <dir>` | Create PRs for migrated repos (interactive: all / selective / one-by-one). |
| `python migrate.py models --subscription <id> --location <region>` | List Azure OpenAI models and Responses API support from ARM. |
| `python migrate.py test` | Run the live Responses API test suite (8 tests). |
| `python migrate.py plan` | Print the recommended migration workflow. |

</details>

<details>
<summary>Repository structure</summary>

```
azure-openai-to-responses/
├── migrate.py                              # CLI entry point
├── pyproject.toml                          # Package metadata & dependencies
├── README.md
├── .github/
│   └── agents/
│       └── azure-openai-to-responses.agent.md  # Copilot agent (orchestrator)
├── skills/
│   └── azure-openai-to-responses/           # Agent Skills-compatible skill
│       ├── SKILL.md                        # Core migration knowledge
│       ├── references/
│       │   ├── cheat-sheet.md              # All code snippets & patterns
│       │   ├── test-migration.md           # Mock, snapshot & assertion updates
│       │   └── troubleshooting.md          # Errors, risk table, gotchas
│       └── scripts/
│           └── detect_legacy.py            # Pattern scanner
├── tools/
│   ├── bulk_migrate.py                     # Bulk workflow: clone, track, send PRs
│   ├── find_legacy_openai_repos.py         # GitHub org search (uses gh CLI)
│   ├── model_compat.py                     # Model compatibility matrix from ARM
│   └── test_migration.py                   # Live API test harness (8 tests)
└── demo/
    └── openai-chat-app-quickstart/         # Fully migrated sample app
        ├── src/quartapp/chat.py            # Migrated backend (AsyncOpenAI + streaming)
        ├── tests/                          # Migrated tests (mocks, snapshots)
        └── infra/aca.bicep                 # Migrated Bicep (env var changes)
```

</details>

<details>
<summary>Environment variables</summary>

| Variable | Used by | Description |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | test | Azure OpenAI resource URL |
| `AZURE_OPENAI_DEPLOYMENT` | test | Deployment name (e.g., `gpt-4o`) |
| `AZURE_OPENAI_API_KEY` | test | API key (omit if using EntraID) |
| `AZURE_TENANT_ID` | EntraID auth | Tenant ID |
| `AZURE_CLIENT_ID` | Managed identity | User-assigned managed identity client ID |

</details>

---

## Contributing

1. Fork the repo
2. Test your changes: `python migrate.py scan . && pytest tools/test_migration.py -v`
3. Submit a PR

## License

MIT
