"""
Find repos in a GitHub org still using legacy OpenAI Chat Completions patterns.

Searches for: AzureOpenAI constructors, chat.completions.create calls,
legacy response shapes (choices[0].message), deprecated parameters, etc.

Prerequisites:
    gh CLI installed and authenticated (gh auth login)

Usage:
    python find_legacy_openai_repos.py --org YOUR_ORG
    python find_legacy_openai_repos.py --org YOUR_ORG --language python
    python find_legacy_openai_repos.py --org YOUR_ORG --language python --json
"""

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict

# Patterns that indicate legacy Chat Completions usage
SEARCH_PATTERNS = [
    ("chat.completions.create", "Chat Completions API call"),
    ("ChatCompletion.create", "Legacy ChatCompletion call"),
    ("AzureOpenAI(", "Deprecated AzureOpenAI constructor"),
    ("AsyncAzureOpenAI(", "Deprecated AsyncAzureOpenAI constructor"),
    ("choices[0].message.content", "Legacy response shape"),
    ("choices[0].delta.content", "Legacy streaming response shape"),
    ("api_version=", "api_version parameter (may be legacy)"),
]

# GitHub code search rate limit: 10 requests per minute for authenticated users
SEARCH_RATE_LIMIT_PAUSE = 7  # seconds between searches to stay under limit


def gh_run(args: list[str]) -> str:
    """Run a gh CLI command and return stdout. Raises on failure."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}... failed: {result.stderr.strip()}")
    return result.stdout


def search_code(org: str, pattern: str, language: str | None) -> list[dict]:
    """Search GitHub code for a pattern within an org using gh CLI. Returns list of match dicts."""
    cmd = [
        "search", "code",
        "--owner", org,
        pattern,
        "--json", "repository,path",
        "--limit", "100",
    ]
    if language:
        cmd.extend(["--language", language])

    try:
        out = gh_run(cmd)
        return json.loads(out) if out.strip() else []
    except RuntimeError as e:
        print(f"  Warning: {e}", file=sys.stderr)
        return []


def get_repo_stars(repo_full_name: str) -> int:
    """Fetch star count for a repo via gh api."""
    try:
        out = gh_run(["api", f"repos/{repo_full_name}", "--jq", ".stargazers_count"])
        return int(out.strip())
    except (RuntimeError, ValueError):
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Find repos in a GitHub org using legacy OpenAI Chat Completions patterns."
    )
    parser.add_argument("--org", required=True, help="GitHub organization name")
    parser.add_argument("--language", default=None, help="Filter by language (e.g., python, typescript)")
    parser.add_argument("--json", dest="output_json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    # Verify gh CLI is authenticated
    try:
        username = gh_run(["api", "/user", "--jq", ".login"]).strip()
    except RuntimeError:
        print("Error: gh CLI not authenticated. Run 'gh auth login' first.", file=sys.stderr)
        sys.exit(1)
    print(f"Authenticated as: {username}", file=sys.stderr)
    print(f"Searching org: {args.org}", file=sys.stderr)
    if args.language:
        print(f"Language filter: {args.language}", file=sys.stderr)
    print(file=sys.stderr)

    # repo_name -> {pattern_label -> [file_paths]}
    repo_matches: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    total_matches = 0

    for pattern, label in SEARCH_PATTERNS:
        print(f"Searching: {pattern!r} ({label})...", file=sys.stderr)
        items = search_code(args.org, pattern, args.language)

        for item in items:
            repo_name = item["repository"]["fullName"]
            file_path = item.get("path", "?")
            repo_matches[repo_name][label].append(file_path)
            total_matches += 1

        print(f"  Found {len(items)} matches across {len({i['repository']['fullName'] for i in items})} repos", file=sys.stderr)

        # Pause between searches to respect rate limits
        time.sleep(SEARCH_RATE_LIMIT_PAUSE)

    print(file=sys.stderr)

    if not repo_matches:
        print("No legacy OpenAI patterns found.", file=sys.stderr)
        sys.exit(0)

    # --- Fetch star counts ---

    print(f"Fetching star counts for {len(repo_matches)} repos...", file=sys.stderr)
    repo_stars: dict[str, int] = {}
    for repo in repo_matches:
        repo_stars[repo] = get_repo_stars(repo)

    # Sort repos by stars descending
    sorted_repos = sorted(repo_matches.keys(), key=lambda r: repo_stars.get(r, 0), reverse=True)

    # --- Output ---

    if args.output_json:
        output = {
            "org": args.org,
            "language_filter": args.language,
            "total_repos": len(repo_matches),
            "total_matches": total_matches,
            "repos": [
                {
                    "repo": repo,
                    "stars": repo_stars.get(repo, 0),
                    "patterns_found": list(repo_matches[repo].keys()),
                    "files": {
                        label: sorted(set(paths))
                        for label, paths in repo_matches[repo].items()
                    },
                }
                for repo in sorted_repos
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Found {total_matches} matches across {len(repo_matches)} repos in '{args.org}' (sorted by ⭐ descending):\n")
        for repo in sorted_repos:
            stars = repo_stars.get(repo, 0)
            patterns = repo_matches[repo]
            unique_files = sorted({f for paths in patterns.values() for f in paths})
            print(f"  {repo}  ⭐ {stars}")
            print(f"    Patterns: {', '.join(sorted(patterns.keys()))}")
            print(f"    Files ({len(unique_files)}):")
            for f in unique_files[:10]:
                print(f"      - {f}")
            if len(unique_files) > 10:
                print(f"      ... and {len(unique_files) - 10} more")
            print()


if __name__ == "__main__":
    main()
