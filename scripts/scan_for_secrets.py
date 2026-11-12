"""Scan the working tree, and optionally the full git history, for credentials.

Run: python scripts/scan_for_secrets.py [--history]

A key found in a repository is a serious finding whether or not it still
works, and deleting it from the working tree does not remove it from the
history. This runs in CI so that the answer is known continuously rather
than discovered the day before submission.

Gitignored files are reported separately and do not fail the scan: a key in
`.env` is a key on somebody's disk, which is where it belongs, and git will
not let it reach the repository. The exit code tracks what could be
committed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATTERNS = {
    "groq_key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "openrouter_key": re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
    "openai_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{32,}"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "storage", ".pytest_cache"}
# This file necessarily contains the patterns it searches for.
SKIP_FILES = {"scan_for_secrets.py"}
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini",
    ".sh", ".env", ".example", "",
}


def scan_text(text: str, where: str) -> list[str]:
    return [
        f"{where}: {name} matched {match.group(0)[:12]}..."
        for name, pattern in PATTERNS.items()
        for match in pattern.finditer(text)
    ]


def git_ignored(relative_paths: list[Path]) -> set[str]:
    if not relative_paths:
        return set()
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=ROOT,
            input="\n".join(str(p) for p in relative_paths),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def scan_tree() -> tuple[list[str], list[str]]:
    """Returns (committable findings, findings in gitignored files)."""
    candidates = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not (set(path.relative_to(ROOT).parts) & SKIP_DIRS)
        and path.name not in SKIP_FILES
        and path.suffix in TEXT_SUFFIXES
        and path.stat().st_size <= 2_000_000
    ]
    ignored = git_ignored([p.relative_to(ROOT) for p in candidates])

    committable: list[str] = []
    protected: list[str] = []
    for path in candidates:
        relative = str(path.relative_to(ROOT))
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = scan_text(text, relative)
        (protected if relative in ignored else committable).extend(hits)
    return committable, protected


def scan_history() -> list[str]:
    try:
        blobs = subprocess.run(
            ["git", "rev-list", "--objects", "--all"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=180,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        print("  (no git history to scan)")
        return []

    findings: list[str] = []
    for line in blobs.splitlines():
        sha, _, name = line.partition(" ")
        if not name or Path(name).suffix not in TEXT_SUFFIXES:
            continue
        if Path(name).name in SKIP_FILES:
            continue
        content = subprocess.run(
            ["git", "cat-file", "-p", sha], cwd=ROOT, capture_output=True, text=True
        ).stdout
        findings += scan_text(content, f"history:{name}@{sha[:8]}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true", help="Also scan every git object.")
    args = parser.parse_args()

    findings, protected = scan_tree()
    if args.history:
        findings += scan_history()

    if protected:
        print("In gitignored files (not committable, no action needed):")
        for item in sorted(set(protected)):
            print(f"  {item}")
        print()

    if findings:
        print("CREDENTIALS THAT COULD REACH THE REPOSITORY:")
        for item in sorted(set(findings)):
            print(f"  {item}")
        return 1

    scope = "working tree and history" if args.history else "working tree"
    print(f"No committable credentials found in the {scope}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
