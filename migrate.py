#!/usr/bin/env python3
"""azure-openai-to-responses — CLI entry point for Azure OpenAI Responses API migration.

One command to scan a codebase for legacy Chat Completions patterns, display
a categorised report, optionally smoke-test the target deployment, and print
a migration plan.

Usage:
    # Scan a directory for legacy patterns
    python migrate.py scan ./my-app

    # Scan and also smoke-test the target Azure OpenAI deployment
    python migrate.py scan ./my-app --smoke-test

    # Search a GitHub org for repos that need migration
    python migrate.py org-scan --org my-org

    # Run the live Responses API test suite against your deployment
    python migrate.py test

    # Print the recommended migration workflow
    python migrate.py plan
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / ".github" / "skills" / "azure-openai-to-responses" / "scripts"
TOOLS = ROOT / "tools"


# ---------------------------------------------------------------------------
# scan — runs detect_legacy.py
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    """Scan directories for legacy Chat Completions patterns."""
    scanner = SCRIPTS / "detect_legacy.py"
    if not scanner.exists():
        print(f"Error: scanner not found at {scanner}", file=sys.stderr)
        return 1

    dirs = args.directories or ["."]
    rc = subprocess.run([sys.executable, str(scanner)] + dirs).returncode

    if args.smoke_test:
        print("\n--- Smoke-testing Azure OpenAI Responses API deployment ---\n")
        rc_smoke = _run_smoke_test()
        return max(rc, rc_smoke)

    return rc


def _run_smoke_test() -> int:
    """Quick smoke test against the configured Azure OpenAI deployment."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")

    if not endpoint:
        print("Error: AZURE_OPENAI_ENDPOINT not set", file=sys.stderr)
        return 1
    if not deployment:
        print("Error: AZURE_OPENAI_DEPLOYMENT not set", file=sys.stderr)
        return 1
    if not api_key:
        print("Warning: AZURE_OPENAI_API_KEY not set — trying EntraID auth", file=sys.stderr)

    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package not installed. Run: pip install openai>=1.108.1", file=sys.stderr)
        return 1

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
            print("Error: azure-identity not installed. Run: pip install azure-identity", file=sys.stderr)
            return 1

    try:
        resp = client.responses.create(
            model=deployment,
            input="Say hello in one word.",
            max_output_tokens=50,
            store=False,
        )
        print(f"[PASS] Deployment '{deployment}' supports Responses API")
        print(f"   Model output: {resp.output_text}")
        print(f"   Status: {resp.status}")
        return 0
    except Exception as e:
        print(f"[FAIL] Deployment '{deployment}' does NOT support Responses API")
        print(f"   Error: {e}")
        return 1


# ---------------------------------------------------------------------------
# org-scan — runs find_legacy_openai_repos.py
# ---------------------------------------------------------------------------

def cmd_org_scan(args: argparse.Namespace) -> int:
    """Search a GitHub org for repos using legacy patterns."""
    script = TOOLS / "find_legacy_openai_repos.py"
    if not script.exists():
        print(f"Error: script not found at {script}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(script), "--org", args.org]
    if args.language:
        cmd.extend(["--language", args.language])
    if args.json:
        cmd.append("--json")

    return subprocess.run(cmd).returncode


# ---------------------------------------------------------------------------
# test — runs the live Responses API test suite
# ---------------------------------------------------------------------------

def cmd_test(args: argparse.Namespace) -> int:
    """Run the live Responses API test harness."""
    test_file = TOOLS / "test_migration.py"
    if not test_file.exists():
        print(f"Error: test harness not found at {test_file}", file=sys.stderr)
        return 1

    cmd = [sys.executable, "-m", "pytest", str(test_file), "-v"]
    return subprocess.run(cmd).returncode


# ---------------------------------------------------------------------------
# plan — print the migration workflow
# ---------------------------------------------------------------------------

def cmd_plan(args: argparse.Namespace) -> int:
    """Print the recommended migration workflow."""
    plan = """
╔══════════════════════════════════════════════════════════════════╗
║           Azure OpenAI → Responses API Migration Plan           ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  APPROACH A: Single-repo migration                               ║
║  ─────────────────────────────────                               ║
║  1. Scan:    python migrate.py scan /path/to/your-app            ║
║  2. Migrate: @azure-openai-to-responses migrate /path/...        ║
║     Or follow .github/skills/azure-openai-to-responses/SKILL.md ║
║  3. Verify:  python migrate.py scan /path/to/your-app            ║
║              cd /path/to/your-app && pytest                      ║
║                                                                  ║
║  APPROACH B: Bulk migration across repos                         ║
║  ───────────────────────────────────────                         ║
║  1. Discover: python migrate.py org-scan --org YOUR_ORG          ║
║  2. Scan:     python migrate.py scan /path/to/each-repo          ║
║  3. Migrate:  Use Approach A per repo, then send PRs             ║
║  4. Track:    Re-run org-scan to see remaining repos             ║
║                                                                  ║
║  APPROACH C: Skill-only (no agent)                               ║
║  ─────────────────────────────────                               ║
║  Feed .github/skills/azure-openai-to-responses/SKILL.md to      ║
║  any LLM (Copilot, Claude, ChatGPT) as context, then ask it     ║
║  to migrate your code.                                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(plan)
    return 0


# ---------------------------------------------------------------------------
# models — delegates to tools/model_compat.py
# ---------------------------------------------------------------------------

def cmd_models(args: argparse.Namespace) -> int:
    """List Azure OpenAI models and their Responses API support."""
    script = TOOLS / "model_compat.py"
    if not script.exists():
        print(f"Error: model_compat.py not found at {script}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(script)] + args.model_args
    return subprocess.run(cmd).returncode


# ---------------------------------------------------------------------------
# bulk — delegates to tools/bulk_migrate.py
# ---------------------------------------------------------------------------

def cmd_bulk(args: argparse.Namespace) -> int:
    """Bulk migration workflow: prepare, status, send-prs across repos."""
    script = TOOLS / "bulk_migrate.py"
    if not script.exists():
        print(f"Error: bulk_migrate.py not found at {script}", file=sys.stderr)
        return 1

    # Forward remaining args to the bulk script
    cmd = [sys.executable, str(script)] + args.bulk_args
    return subprocess.run(cmd).returncode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Commands that delegate all args directly to a sub-script.
# We intercept these before argparse to avoid flag conflicts.
_DELEGATE_COMMANDS = {
    "models": ("model_compat.py", TOOLS),
    "bulk": ("bulk_migrate.py", TOOLS),
}


def main() -> int:
    # Fast-path: delegated commands forward all remaining args to their script
    if len(sys.argv) >= 2 and sys.argv[1] in _DELEGATE_COMMANDS:
        script_name, script_dir = _DELEGATE_COMMANDS[sys.argv[1]]
        script = script_dir / script_name
        if not script.exists():
            print(f"Error: {script_name} not found at {script}", file=sys.stderr)
            return 1
        return subprocess.run([sys.executable, str(script)] + sys.argv[2:]).returncode

    parser = argparse.ArgumentParser(
        prog="azure-openai-to-responses",
        description="Azure OpenAI Chat Completions → Responses API migration toolkit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="Scan directories for legacy Chat Completions patterns")
    p_scan.add_argument("directories", nargs="*", help="Directories to scan (default: .)")
    p_scan.add_argument("--smoke-test", action="store_true", help="Also smoke-test the Azure OpenAI deployment")
    p_scan.set_defaults(func=cmd_scan)

    # org-scan
    p_org = sub.add_parser("org-scan", help="Search a GitHub org for repos needing migration")
    p_org.add_argument("--org", required=True, help="GitHub organization name")
    p_org.add_argument("--language", help="Filter by language (e.g., python)")
    p_org.add_argument("--json", action="store_true", help="Output as JSON")
    p_org.set_defaults(func=cmd_org_scan)

    # test
    p_test = sub.add_parser("test", help="Run the live Responses API test suite")
    p_test.set_defaults(func=cmd_test)

    # plan
    p_plan = sub.add_parser("plan", help="Print the recommended migration workflow")
    p_plan.set_defaults(func=cmd_plan)

    # Register delegated commands for --help visibility
    sub.add_parser("bulk", help="Bulk migration: prepare repos, track status, send PRs")
    sub.add_parser("models", help="List Azure OpenAI models and Responses API support")

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
