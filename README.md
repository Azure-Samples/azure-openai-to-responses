# Azure OpenAI To Responses

Migrate your Python apps from the **AzureOpenAI client with Chat Completions API** to the **OpenAI client with Responses API**.

> **GPT-5 and newer models require the Responses API.** Migrating now future-proofs your apps and unlocks deep tool integration, structured output, and a stable `/openai/v1/` endpoint with no `api_version` management.

> **⚠️ Before you start:** Check that your deployed model supports the Responses API — run `python migrate.py models --subscription YOUR_SUB_ID --location YOUR_REGION` or see the [model compatibility](#model-compatibility) section. Older models like `gpt-4o` support Responses but **not all features** (see [known limitations](#known-limitations-with-older-models)).

### What changes?

| Before (Chat Completions) | After (Responses API) |
|---|---|
| `AzureOpenAI()` / `AsyncAzureOpenAI()` | `OpenAI(base_url=...)` / `AsyncOpenAI(base_url=...)` |
| `client.chat.completions.create(messages=...)` | `client.responses.create(input=...)` |
| `resp.choices[0].message.content` | `resp.output_text` |
| `api_version="2024-12-01-preview"` | Not needed — `/openai/v1/` is stable |

---

## Choose your approach

| Approach | Best for | Time |
|---|---|---|
| **[A. Single-repo migration](#a-single-repo-migration)** | One app, hands-on walkthrough | ~30 min per app |
| **[B. Bulk migration across repos](#b-bulk-migration-across-repos)** | Org-wide rollout, multiple repos | Hours (scripted) |
| **[C. Skill-only (no agent)](#c-skill-only-no-agent)** | Any LLM, manual, or custom workflow | Varies |

### Setup (all approaches)

```bash
git clone https://github.com/YOUR_ORG/azure-openai-to-responses.git
cd azure-openai-to-responses
pip install -e ".[dev]"
```

---

## A. Single-repo migration

Migrate one app end-to-end — the same workflow used to migrate the included [demo app](demo/openai-chat-app-quickstart/).

### Step 1 — Scan for legacy patterns

```bash
python migrate.py scan /path/to/your-app
```

The scanner finds every call site that needs to change, grouped by category: client constructors, API calls, response shapes, parameters, env vars, and test infrastructure.

### Step 2 — Let the agent migrate it

Open your app in VS Code as a **multi-root workspace** with both this repo and your app:

1. Open your app folder in VS Code (`File > Open Folder`)
2. Add this repo: `File > Add Folder to Workspace...` → select the cloned `azure-openai-to-responses` folder
3. VS Code switches to an "Untitled (Workspace)" with both folders in the sidebar

> **Why multi-root?** VS Code scopes Copilot's file access to workspace folders. Without this, the agent will prompt for permission every time it tries to read or edit files in your app. Adding both folders to the same workspace avoids those prompts.
>
> **Tip:** Save it for reuse with `File > Save Workspace As...` (creates a `.code-workspace` file you can double-click next time).

In Copilot Chat:

```
@azure-openai-to-responses migrate the app at /path/to/your-app
```

The agent will:
1. **Scan** your code and show what needs to change
2. **Plan** the edit order — constructors first, then API calls, response shapes, tests, cleanup
3. **Migrate** each file with precise, reviewable edits
4. **Verify** by re-running the scanner (zero hits) and your tests (`pytest`)
5. **Report** a summary of everything changed and any manual follow-ups

> **Prefer hands-on?** Skip the agent and follow [SKILL.md](.github/skills/azure-openai-to-responses/SKILL.md) step by step.  The [cheat sheet](.github/skills/azure-openai-to-responses/references/cheat-sheet.md) has copy-paste code for every pattern.

### Step 3 — Verify

```bash
# Scanner should report zero hits
python migrate.py scan /path/to/your-app

# Run your repo's own tests
cd /path/to/your-app && pytest
```

Verification will vary by repo — run whatever unit/integration tests the project already has. If the app has a UI or API endpoint, do a quick manual test too (start the server, send a request, confirm streaming works).

### Demo: what a migrated app looks like

The [`demo/openai-chat-app-quickstart/`](demo/openai-chat-app-quickstart/) directory is a fully migrated [Azure Samples chat app](https://github.com/Azure-Samples/openai-chat-app-quickstart) — a real Quart (async Flask) app.

| File | What changed |
|---|---|
| `src/quartapp/chat.py` | `AsyncAzureOpenAI` → `AsyncOpenAI`, `chat.completions.create` → `responses.create`, streaming rewritten |
| `tests/conftest.py` | `ChatCompletionChunk` mocks → `MockResponseEvent` / `AsyncResponseIterator` |
| `tests/test_app.py` | Assertions updated to `isinstance(client, AsyncOpenAI)` |
| `tests/snapshots/` | `choices[0].delta.content` → `{"delta": {"content": "..."}}` |
| `infra/*.bicep`, `.env.sample` | Removed `AZURE_OPENAI_API_VERSION` / `openAiApiVersion`; added `AZURE_CLIENT_ID` |

**Result:** 4 pytest tests pass (99% coverage), live streaming works end-to-end, scanner reports zero legacy hits.

---

## B. Bulk migration across repos

Roll out the migration across your entire GitHub org with a single workflow that discovers, clones, tracks, and sends PRs.

Requires the [`gh` CLI](https://cli.github.com/), authenticated (`gh auth login`).

### Step 1 — Prepare (discover + clone + scan)

```bash
python migrate.py bulk prepare --org YOUR_ORG
python migrate.py bulk prepare --org YOUR_ORG --language python --workdir ./migrations
```

This automatically:
- Searches your org for repos with legacy Chat Completions patterns
- Clones each repo into the work directory
- Creates a `azure-openai-to-responses-api` branch in each
- Runs the scanner and produces a consolidated report

### Step 2 — Migrate each repo

For each repo in the work directory, pick your method:

- **Agent:** Open the repo in VS Code → `@azure-openai-to-responses migrate this app`
- **Skill:** Feed [SKILL.md](.github/skills/azure-openai-to-responses/SKILL.md) to your LLM
- **Manual:** Follow the skill step-by-step with the [cheat sheet](.github/skills/azure-openai-to-responses/references/cheat-sheet.md)

### Step 3 — Review status

```bash
python migrate.py bulk status --workdir ./migrations
```

Produces a report showing every repo with:
- Migration status (scanned / in-progress / ready / PR sent)
- Files changed in each repo
- Whether the scanner still finds legacy hits

### Step 4 — Send PRs (all at once, selectively, or one-by-one)

```bash
# Send PRs for all repos that are ready (interactive prompt)
python migrate.py bulk send-prs --workdir ./migrations

# Send PRs for specific repos only
python migrate.py bulk send-prs --workdir ./migrations --repos repo1,repo2

# Send PRs for all except some
python migrate.py bulk send-prs --workdir ./migrations --exclude repo3,repo4

# Skip confirmation
python migrate.py bulk send-prs --workdir ./migrations --yes
```

When prompted, you can choose:
- **`y`** — send all PRs
- **`one-by-one`** — review and approve each repo individually
- **`N`** — abort

---

## C. Skill-only (no agent)

The migration knowledge lives in a self-contained [SKILL.md](.github/skills/azure-openai-to-responses/SKILL.md) that any LLM can follow — no VS Code agent required.

### With VS Code Copilot Chat

Add to your `.github/copilot-instructions.md`:

```markdown
When asked to migrate from Chat Completions to Responses API, follow:
.github/skills/azure-openai-to-responses/SKILL.md
```

Then ask: *"Migrate this file from Chat Completions to Responses API."*

### With Claude, ChatGPT, or any LLM

Paste the skill file as context:

```bash
cat .github/skills/azure-openai-to-responses/SKILL.md
```

The skill includes:
- Step-by-step migration instructions with parameter mapping tables
- Client constructor patterns (sync, async, EntraID, API key, multi-tenant)
- Acceptance criteria checklist (code, tests, behavioral gates)
- Links to [cheat-sheet.md](.github/skills/azure-openai-to-responses/references/cheat-sheet.md) (all code snippets), [test-migration.md](.github/skills/azure-openai-to-responses/references/test-migration.md) (mock/snapshot rewrites), and [troubleshooting.md](.github/skills/azure-openai-to-responses/references/troubleshooting.md) (common errors + gotchas)

### Scanner standalone

The scanner works independently — no agent or LLM needed:

```bash
python migrate.py scan /path/to/your-app

# Or call the script directly
python .github/skills/azure-openai-to-responses/scripts/detect_legacy.py /path/to/your-app
```

---

## Model compatibility

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
| Temperature constraints | When migrating to `gpt-5`, temperature must be omitted or set to `1`. Older models have no such constraint. |
| `max_output_tokens` | Minimum is **16** on Azure OpenAI. Values below 16 return a 400 error. |

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
│   ├── agents/
│   │   └── azure-openai-to-responses.agent.md  # Copilot agent (orchestrator)
│   └── skills/
│       └── azure-openai-to-responses/
│           ├── SKILL.md                    # Core migration knowledge
│           ├── references/
│           │   ├── cheat-sheet.md          # All code snippets & patterns
│           │   ├── test-migration.md       # Mock, snapshot & assertion updates
│           │   └── troubleshooting.md      # Errors, risk table, gotchas
│           └── scripts/
│               └── detect_legacy.py        # Pattern scanner
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
