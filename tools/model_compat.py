"""
List Azure OpenAI models and their Responses API / feature support.

Queries the Azure Cognitive Services Management API (ARM) to get model
capabilities per region, then displays a compatibility matrix.

Prerequisites:
    pip install azure-identity azure-mgmt-cognitiveservices

Usage:
    # List all models with Responses API support in a region
    python tools/model_compat.py --subscription SUB_ID --location eastus2

    # Show ALL OpenAI models (including those without Responses)
    python tools/model_compat.py --subscription SUB_ID --location eastus2 --all

    # Filter to specific model families
    python tools/model_compat.py --subscription SUB_ID --location eastus2 --filter gpt-4o,gpt-5,o3

    # Output JSON for scripting
    python tools/model_compat.py --subscription SUB_ID --location eastus2 --json

    # Use tenant ID for cross-tenant auth
    python tools/model_compat.py --subscription SUB_ID --location eastus2 --tenant TENANT_ID

Environment variables (alternative to CLI args):
    AZURE_SUBSCRIPTION_ID   Azure subscription ID
    AZURE_LOCATION          Azure region (e.g., eastus2)
    AZURE_TENANT_ID         Tenant ID (optional)
"""

import argparse
import json
import os
import sys
from collections import defaultdict


def get_models(subscription_id: str, location: str, tenant_id: str | None = None) -> list[dict]:
    """Fetch OpenAI models and capabilities from ARM."""
    try:
        from azure.identity import DefaultAzureCredential, AzureDeveloperCliCredential
        from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
    except ImportError:
        print("Error: required packages not installed. Run:", file=sys.stderr)
        print("  pip install azure-identity azure-mgmt-cognitiveservices", file=sys.stderr)
        sys.exit(1)

    if tenant_id:
        cred = AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
    else:
        cred = DefaultAzureCredential()

    client = CognitiveServicesManagementClient(cred, subscription_id)

    raw_models = list(client.models.list(location=location))

    # Filter to OpenAI format, deduplicate by (name, version)
    seen = set()
    models = []
    for m in raw_models:
        if not m.model or m.model.format != "OpenAI":
            continue
        key = (m.model.name, m.model.version)
        if key in seen:
            continue
        seen.add(key)

        caps = dict(m.model.capabilities) if m.model.capabilities else {}
        models.append({
            "name": m.model.name,
            "version": m.model.version,
            "responses": caps.get("responses", "false") == "true",
            "chatCompletion": caps.get("chatCompletion", "false") == "true",
            "jsonSchemaResponse": caps.get("jsonSchemaResponse", "false") == "true",
            "jsonObjectResponse": caps.get("jsonObjectResponse", "false") == "true",
            "agentsV2": caps.get("agentsV2", "false") == "true",
            "assistants": caps.get("assistants", "false") == "true",
            "fineTune": caps.get("fineTune", "false") == "true" or caps.get("globalFineTune", "false") == "true",
            "realtime": caps.get("realtime", "false") == "true",
            "audio": caps.get("audio", "false") == "true",
            "maxContextToken": caps.get("maxContextToken"),
            "maxOutputToken": caps.get("maxOutputToken"),
            "raw_capabilities": caps,
        })

    # Sort: responses-capable first, then by name, then by version descending
    models.sort(key=lambda m: (not m["responses"], m["name"], m["version"]))
    return models


def print_table(models: list[dict], location: str, show_all: bool) -> None:
    """Print a formatted compatibility matrix."""
    if not show_all:
        models = [m for m in models if m["responses"]]

    if not models:
        print("No models found matching criteria.")
        return

    # Header
    print()
    print(f"  Azure OpenAI Model Compatibility — {location}")
    print(f"  {'='*90}")
    print()

    # Column headers
    hdr = (
        f"  {'Model':<30} {'Version':<12} "
        f"{'Responses':>9} {'Chat':>5} {'JSON Schema':>12} "
        f"{'Agents':>7} {'Fine-tune':>10}"
    )
    print(hdr)
    print(f"  {'-'*30} {'-'*12} {'-'*9} {'-'*5} {'-'*12} {'-'*7} {'-'*10}")

    for m in models:
        flag = lambda v: "Y" if v else "-"
        row = (
            f"  {m['name']:<30} {m['version']:<12} "
            f"{flag(m['responses']):>9} {flag(m['chatCompletion']):>5} "
            f"{flag(m['jsonSchemaResponse'] or m['jsonObjectResponse']):>12} "
            f"{flag(m['agentsV2']):>7} {flag(m['fineTune']):>10}"
        )
        print(row)

    # Summary
    responses_count = sum(1 for m in models if m["responses"])
    total = len(models)
    print()
    print(f"  {responses_count}/{total} model versions support the Responses API in {location}")

    # Migration notes
    responses_models = [m for m in models if m["responses"]]
    no_json_schema = [m for m in responses_models if not m["jsonSchemaResponse"] and not m["jsonObjectResponse"]]
    no_agents = [m for m in responses_models if not m["agentsV2"]]

    if no_json_schema or no_agents:
        print()
        print("  Notes:")
        if no_json_schema:
            names = sorted({m["name"] for m in no_json_schema})
            print(f"    - JSON Schema not declared for: {', '.join(names)}")
            print(f"      (structured output via text.format may still work — test with your deployment)")
        if no_agents:
            names = sorted({m["name"] for m in no_agents})
            print(f"    - Agents V2 not declared for: {', '.join(names)}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List Azure OpenAI models and their Responses API / feature support."
    )
    parser.add_argument(
        "--subscription", default=os.environ.get("AZURE_SUBSCRIPTION_ID"),
        help="Azure subscription ID (or set AZURE_SUBSCRIPTION_ID)"
    )
    parser.add_argument(
        "--location", default=os.environ.get("AZURE_LOCATION", "eastus2"),
        help="Azure region (default: eastus2, or set AZURE_LOCATION)"
    )
    parser.add_argument(
        "--tenant", default=os.environ.get("AZURE_TENANT_ID"),
        help="Tenant ID for cross-tenant auth (or set AZURE_TENANT_ID)"
    )
    parser.add_argument(
        "--all", dest="show_all", action="store_true",
        help="Show all OpenAI models (default: only Responses-capable)"
    )
    parser.add_argument(
        "--filter", dest="name_filter",
        help="Comma-separated model name prefixes to include (e.g., gpt-4o,gpt-5,o3)"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true",
        help="Output as JSON"
    )
    args = parser.parse_args()

    if not args.subscription:
        print("Error: --subscription required (or set AZURE_SUBSCRIPTION_ID)", file=sys.stderr)
        return 1

    models = get_models(args.subscription, args.location, args.tenant)

    # Apply name filter
    if args.name_filter:
        prefixes = [p.strip().lower() for p in args.name_filter.split(",")]
        models = [m for m in models if any(m["name"].lower().startswith(p) for p in prefixes)]

    if args.output_json:
        # Strip raw_capabilities for cleaner JSON
        output = []
        for m in models:
            entry = {k: v for k, v in m.items() if k != "raw_capabilities"}
            output.append(entry)
        print(json.dumps({"location": args.location, "models": output}, indent=2))
    else:
        print_table(models, args.location, args.show_all)

    return 0


if __name__ == "__main__":
    sys.exit(main())
