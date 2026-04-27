#!/usr/bin/env python3
"""MCP server for the Azure OpenAI → Responses API migration toolkit.

Exposes the scanner, smoke test, model compatibility checker, and migration
plan as structured MCP tools that agents can call natively instead of shelling
out to CLI scripts.

Usage:
    # stdio transport (default for VS Code, Claude Code, etc.)
    python mcp_server.py

    # Or via the installed entry point
    azure-openai-to-responses-mcp
"""

import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Reuse the existing scanner module directly
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "skills" / "azure-openai-to-responses" / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import detect_legacy  # noqa: E402

mcp = FastMCP(
    "azure-openai-to-responses",
    instructions="Migrate Python apps from Azure OpenAI Chat Completions to the Responses API",
)


# ---------------------------------------------------------------------------
# Tool: scan
# ---------------------------------------------------------------------------

@mcp.tool()
def scan(directories: list[str]) -> dict:
    """Scan directories for legacy Azure OpenAI Chat Completions patterns.

    Returns a structured report of all legacy patterns found, grouped by
    category (api-call, client, response-shape, parameter, env-var, test).
    Use this before migrating to understand what needs to change.

    Args:
        directories: List of directory paths to scan. Use ["."] for current directory.
    """
    all_results: dict[str, list[tuple[int, str, str, str]]] = {}
    errors: list[str] = []

    for d in directories:
        root = Path(d)
        if not root.is_dir():
            errors.append(f"{d} is not a directory")
            continue
        all_results.update(detect_legacy.scan_directory(root))

    # Build structured output
    total = 0
    categories: dict[str, list[dict]] = {}

    for filepath, hits in all_results.items():
        for line_no, line_text, description, category in hits:
            categories.setdefault(category, []).append({
                "file": filepath,
                "line": line_no,
                "text": line_text[:200],
                "description": description,
            })
            total += 1

    return {
        "total_hits": total,
        "files_affected": len(all_results),
        "categories": categories,
        "clean": total == 0,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Tool: smoke_test
# ---------------------------------------------------------------------------

@mcp.tool()
def smoke_test() -> dict:
    """Smoke-test the configured Azure OpenAI deployment for Responses API support.

    Sends a minimal request to the Responses API endpoint and reports whether
    the deployment supports it. Requires AZURE_OPENAI_ENDPOINT and
    AZURE_OPENAI_DEPLOYMENT environment variables. Uses AZURE_OPENAI_API_KEY
    if set, otherwise falls back to Entra ID (DefaultAzureCredential).
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")

    if not endpoint:
        return {"success": False, "error": "AZURE_OPENAI_ENDPOINT not set"}
    if not deployment:
        return {"success": False, "error": "AZURE_OPENAI_DEPLOYMENT not set"}

    try:
        from openai import OpenAI
    except ImportError:
        return {"success": False, "error": "openai package not installed (need >=1.108.1)"}

    base_url = f"{endpoint.rstrip('/')}/openai/v1/"

    if api_key:
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        try:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            client = OpenAI(api_key=token_provider, base_url=base_url)
        except ImportError:
            return {"success": False, "error": "azure-identity not installed and no API key set"}

    try:
        resp = client.responses.create(
            model=deployment,
            input="Say hello in one word.",
            max_output_tokens=50,
            store=False,
        )
        return {
            "success": True,
            "deployment": deployment,
            "output": resp.output_text,
            "status": resp.status,
        }
    except Exception as e:
        return {
            "success": False,
            "deployment": deployment,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Tool: check_models
# ---------------------------------------------------------------------------

@mcp.tool()
def check_models(
    subscription_id: str,
    location: str = "eastus2",
    name_filter: str | None = None,
    show_all: bool = False,
) -> dict:
    """List Azure OpenAI models and their Responses API / feature support.

    Queries Azure ARM to get live model capabilities for a specific region.
    Returns which models support the Responses API, structured output, agents, etc.

    Args:
        subscription_id: Azure subscription ID.
        location: Azure region (e.g., eastus2, westus3).
        name_filter: Comma-separated model name prefixes to include (e.g., "gpt-4o,gpt-5,o3").
        show_all: If True, include models without Responses API support.
    """
    try:
        import model_compat
    except ImportError:
        return {"error": "model_compat module not found"}

    try:
        models = model_compat.get_models(subscription_id, location)
    except Exception as e:
        return {"error": str(e)}

    if name_filter:
        prefixes = [p.strip().lower() for p in name_filter.split(",")]
        models = [m for m in models if any(m["name"].lower().startswith(p) for p in prefixes)]

    if not show_all:
        models = [m for m in models if m["responses"]]

    # Strip raw_capabilities for cleaner output
    clean = [{k: v for k, v in m.items() if k != "raw_capabilities"} for m in models]

    responses_count = sum(1 for m in clean if m["responses"])
    return {
        "location": location,
        "models": clean,
        "total": len(clean),
        "responses_capable": responses_count,
    }


# ---------------------------------------------------------------------------
# Tool: migration_plan
# ---------------------------------------------------------------------------

@mcp.tool()
def migration_plan() -> dict:
    """Get the recommended migration workflow for moving from Chat Completions to Responses API.

    Returns structured migration steps for single-repo, bulk, and skill-only approaches.
    """
    return {
        "approaches": [
            {
                "name": "Single-repo migration",
                "steps": [
                    "Scan: use the 'scan' tool to find legacy patterns",
                    "Migrate: apply edits following SKILL.md (client constructors → API calls → response shapes → tests → env vars)",
                    "Verify: re-run 'scan' (expect zero hits) and run the repo's test suite",
                ],
            },
            {
                "name": "Bulk migration across repos",
                "steps": [
                    "Discover: python migrate.py org-scan --org YOUR_ORG",
                    "Scan each repo with the 'scan' tool",
                    "Migrate each repo using single-repo approach",
                    "Send PRs: python migrate.py bulk send-prs --workdir ./migrations",
                ],
            },
            {
                "name": "Skill-only (no agent)",
                "steps": [
                    "Feed skills/azure-openai-to-responses/SKILL.md as context to any LLM",
                    "Ask the LLM to migrate your code following the skill instructions",
                ],
            },
        ],
        "key_mappings": {
            "AzureOpenAI()": "OpenAI(base_url=f'{endpoint}/openai/v1/')",
            "AsyncAzureOpenAI()": "AsyncOpenAI(base_url=f'{endpoint}/openai/v1/')",
            "chat.completions.create(messages=...)": "responses.create(input=...)",
            "choices[0].message.content": "output_text",
            "api_version": "Not needed (v1 endpoint is stable)",
        },
    }


if __name__ == "__main__":
    mcp.run()


def run():
    """Entry point for pyproject.toml console_scripts."""
    mcp.run()
