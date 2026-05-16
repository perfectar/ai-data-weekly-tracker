#!/usr/bin/env python3
"""Local weekly agent: fetch papers, rebuild site, commit, and push."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"$ {' '.join(command)}")
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def has_git_repo() -> bool:
    return (ROOT / ".git").exists()


def has_remote() -> bool:
    result = run(["git", "remote", "get-url", "origin"], check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def has_changes() -> bool:
    result = run(["git", "status", "--porcelain"], check=False)
    return bool(result.stdout.strip())


def commit_and_push(push: bool) -> None:
    if not has_git_repo():
        print("No .git directory found; skip commit and push.")
        return

    run(["git", "add", "README.md", "index.html", "data", "weekly", "scripts"])
    if not has_changes():
        print("No changes detected; skip commit.")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run(["git", "commit", "-m", f"Update AI data weekly brief ({stamp})"])

    if push:
        if not has_remote():
            print("No origin remote configured; skip push.")
            return
        run(["git", "push", "origin", "main"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fetch", action="store_true", help="Only rebuild site and commit existing files.")
    parser.add_argument("--no-push", action="store_true", help="Do not push to origin after committing.")
    parser.add_argument("--end-date", help="Override weekly end date in YYYY-MM-DD.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.no_fetch:
        update_cmd = [sys.executable, "scripts/update_weekly.py"]
        if args.end_date:
            update_cmd.extend(["--end-date", args.end_date])
        update_result = run(update_cmd)
        print(update_result.stdout)

    build_result = run([sys.executable, "scripts/build_site.py"])
    print(build_result.stdout)

    commit_and_push(push=not args.no_push)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
