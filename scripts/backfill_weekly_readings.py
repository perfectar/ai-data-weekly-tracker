#!/usr/bin/env python3
"""Backfill Chinese readings into existing weekly Markdown reports."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from update_weekly import Paper, clean_text, infer_chinese_reading


ROOT = Path(__file__).resolve().parents[1]
WEEKLY_DIR = ROOT / "weekly"
READING_HEADING = "**中文解读与航空 AI 数据启示**"


def field_value(block: str, label: str) -> str:
    pattern = rf"^- \*\*{re.escape(label)}\*\*：(.+)$"
    match = re.search(pattern, block, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def extract_between(block: str, start_marker: str, end_marker: str) -> str:
    start = block.find(start_marker)
    end = block.find(end_marker)
    if start == -1 or end == -1 or end <= start:
        return ""
    return block[start + len(start_marker) : end].strip()


def parse_paper(block: str) -> Paper:
    title_match = re.search(r"^### \d+\. (.+)$", block, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Untitled"
    published_raw = field_value(block, "日期")
    published = date.fromisoformat(published_raw) if published_raw else date.today()
    keyword_text = field_value(block, "关键词")
    keywords = [item.strip() for item in re.split(r"[、,]", keyword_text) if item.strip() and item.strip() != "N/A"]
    authors = [item.strip() for item in field_value(block, "作者").split(",") if item.strip() and item.strip() != "N/A"]
    summary = clean_text(extract_between(block, "**摘要摘录**", "**数据角度初判**"))

    return Paper(
        title=title,
        authors=authors,
        summary=summary,
        url=field_value(block, "链接"),
        published=published,
        category=field_value(block, "类别"),
        score=0,
        matched_keywords=keywords,
    )


def add_reading_to_block(block: str) -> tuple[str, bool]:
    if READING_HEADING in block:
        return block, False
    if "**数据角度初判**" not in block:
        return block, False

    tail = ""
    follow_up_index = block.find("\n## 下周跟进")
    if follow_up_index != -1:
        tail = block[follow_up_index:]
        block = block[:follow_up_index]

    paper = parse_paper(block)
    reading = infer_chinese_reading(paper)
    enriched = block.rstrip() + f"\n\n{READING_HEADING}\n\n{reading}\n"
    return enriched + tail, True


def backfill_markdown(markdown: str) -> tuple[str, int]:
    matches = list(re.finditer(r"(?m)^### \d+\. .+$", markdown))
    if not matches:
        return markdown, 0

    chunks: list[str] = [markdown[: matches[0].start()]]
    changed_count = 0
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        updated, changed = add_reading_to_block(markdown[match.start() : end])
        chunks.append(updated)
        if changed:
            changed_count += 1
    return "".join(chunks), changed_count


def main() -> int:
    total = 0
    for path in sorted(WEEKLY_DIR.glob("*.md")):
        markdown = path.read_text(encoding="utf-8")
        updated, changed_count = backfill_markdown(markdown)
        if changed_count:
            path.write_text(updated, encoding="utf-8")
            print(f"Backfilled {path.relative_to(ROOT)}: {changed_count} paper(s)")
            total += changed_count
    print(f"Backfilled {total} paper reading(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
