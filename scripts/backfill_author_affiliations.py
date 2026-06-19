#!/usr/bin/env python3
"""Backfill author affiliations in existing weekly Markdown reports."""

from __future__ import annotations

import re
import argparse
from datetime import date
from pathlib import Path

from update_weekly import (
    Paper,
    fetch_openalex_work,
    format_author_affiliations,
    openalex_affiliation_from_authorship,
)


ROOT = Path(__file__).resolve().parents[1]
WEEKLY_DIR = ROOT / "weekly"
FALLBACK_PREFIX = "arXiv 未提供作者单位"


def field_value(block: str, label: str) -> str:
    pattern = rf"^- \*\*{re.escape(label)}\*\*：(.+)$"
    match = re.search(pattern, block, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_title(block: str) -> str:
    match = re.search(r"^### \d+\. (.+)$", block, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_authors(block: str) -> list[str]:
    return [
        author.strip()
        for author in field_value(block, "作者").split(",")
        if author.strip() and author.strip() != "N/A" and author.strip() != "et al."
    ]


def affiliations_for(title: str, authors: list[str]) -> list[str]:
    work = fetch_openalex_work(title)
    if not work:
        return []

    affiliations = [
        openalex_affiliation_from_authorship(authorship)
        for authorship in work.get("authorships", [])
    ]
    return affiliations[: len(authors)]


def update_affiliation_line(block: str) -> tuple[str, bool]:
    title = parse_title(block)
    authors = parse_authors(block)
    if not title or not authors:
        return block, False

    existing = field_value(block, "作者单位")
    if existing and not existing.startswith(FALLBACK_PREFIX):
        return block, False

    affiliations = affiliations_for(title, authors)
    if not any(affiliation.strip() for affiliation in affiliations):
        affiliations = []

    paper = Paper(
        title=title,
        authors=authors,
        author_affiliations=affiliations,
        summary="",
        url=field_value(block, "链接"),
        published=date.today(),
        category=field_value(block, "类别"),
        score=0,
        matched_keywords=[],
    )
    line = f"- **作者单位**：{format_author_affiliations(paper)}"

    existing_match = re.search(r"^- \*\*作者单位\*\*：.+$", block, flags=re.MULTILINE)
    if existing_match:
        if existing_match.group(0) == line:
            return block, False
        updated = block[: existing_match.start()] + line + block[existing_match.end() :]
        return updated, True

    author_match = re.search(r"^- \*\*作者\*\*：.+$", block, flags=re.MULTILINE)
    if not author_match:
        return block, False
    updated = block[: author_match.end()] + "\n" + line + block[author_match.end() :]
    return updated, True


def backfill_markdown(markdown: str) -> tuple[str, int]:
    matches = list(re.finditer(r"(?m)^### \d+\. .+$", markdown))
    if not matches:
        return markdown, 0

    chunks: list[str] = [markdown[: matches[0].start()]]
    changed_count = 0
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        updated, changed = update_affiliation_line(markdown[match.start() : end])
        chunks.append(updated)
        if changed:
            changed_count += 1
    return "".join(chunks), changed_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", help="Only backfill one ISO week, for example 2026-W24.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = [WEEKLY_DIR / f"{args.week}.md"] if args.week else sorted(WEEKLY_DIR.glob("*.md"))

    total = 0
    for path in paths:
        if not path.exists():
            print(f"Skipped missing {path.relative_to(ROOT)}")
            continue
        print(f"Processing {path.relative_to(ROOT)}...", flush=True)
        markdown = path.read_text(encoding="utf-8")
        updated, changed_count = backfill_markdown(markdown)
        if changed_count:
            path.write_text(updated, encoding="utf-8")
            print(f"Backfilled {path.relative_to(ROOT)}: {changed_count} affiliation line(s)")
            total += changed_count
    print(f"Backfilled {total} affiliation line(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
