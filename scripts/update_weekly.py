#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import textwrap
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEEKLY_DIR = ROOT / "weekly"
DATA_DIR = ROOT / "data"
WEEKS_JSON = DATA_DIR / "weeks.json"
ARXIV_API = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
CATEGORY_QUERY = "(cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:cs.CV OR cat:stat.ML)"

KEYWORDS = {
    "data selection": 5, "data curation": 5, "data quality": 5,
    "dataset": 4, "benchmark": 3, "synthetic data": 5,
    "generated data": 4, "training data": 5, "pretraining data": 5,
    "post-training data": 5, "instruction data": 5, "data mixture": 4,
    "data filtering": 5, "data governance": 5, "data lineage": 5,
    "data contamination": 5, "annotation": 4, "labelled data": 4,
    "labeled data": 4, "data scarcity": 4, "corpus": 4,
    "multilingual data": 4, "tabular data": 4, "privacy": 3,
    "pii": 5, "bias dataset": 4, "tool-calling dataset": 5,
}
TREND_RULES = {
    "数据选择与过滤": ["data selection", "data filtering", "data mixture", "pretraining data"],
    "合成数据与自生成数据": ["synthetic data", "generated data", "self-generated"],
    "数据集与基准": ["dataset", "benchmark", "corpus"],
    "标注、隐私与安全数据": ["annotation", "labelled data", "labeled data", "pii", "privacy", "bias"],
    "数据治理与血缘": ["data governance", "data lineage", "contamination"],
    "表格、语音与非文本数据": ["tabular", "speech", "audio", "multimodal"],
}

@dataclass
class Paper:
    title: str
    authors: list[str]
    summary: str
    url: str
    published: date
    category: str
    score: int
    matched_keywords: list[str]

def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()

def score_paper(title: str, summary: str) -> tuple[int, list[str]]:
    text = f"{title}\n{summary}".lower()
    matched = [key for key in KEYWORDS if key in text]
    return sum(KEYWORDS[key] for key in matched), matched

def fetch_arxiv(max_results: int = 250, retries: int = 3) -> list[Paper]:
    params = {
        "search_query": CATEGORY_QUERY,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                root = ET.fromstring(response.read())
            papers: list[Paper] = []
            for entry in root.findall("atom:entry", NS):
                title = clean(entry.findtext("atom:title", default="", namespaces=NS))
                summary = clean(entry.findtext("atom:summary", default="", namespaces=NS))
                raw_date = entry.findtext("atom:published", default="", namespaces=NS)
                if not title or not summary or not raw_date:
                    continue
                authors = [clean(a.findtext("atom:name", default="", namespaces=NS)) for a in entry.findall("atom:author", NS)]
                authors = [a for a in authors if a]
                url_value = clean(entry.findtext("atom:id", default="", namespaces=NS))
                primary = entry.find("arxiv:primary_category", NS)
                category = primary.attrib.get("term", "") if primary is not None else ""
                score, matched = score_paper(title, summary)
                papers.append(Paper(title, authors, summary, url_value, datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date(), category, score, matched))
            return papers
        except Exception as exc:
            last_error = exc
            time.sleep(2 + attempt * 2)
    raise RuntimeError(f"Failed to fetch arXiv feed: {last_error}")

def make_week_label(end_date: date) -> str:
    year, week, _ = end_date.isocalendar()
    return f"{year}-W{week:02d}"

def filter_weekly(papers: list[Paper], start_date: date, end_date: date) -> list[Paper]:
    selected = []
    seen = set()
    for paper in papers:
        if paper.url in seen:
            continue
        seen.add(paper.url)
        if start_date <= paper.published <= end_date and paper.score >= 4:
            selected.append(paper)
    selected.sort(key=lambda item: (item.score, item.published), reverse=True)
    return selected[:20]

def trend_counts(papers: list[Paper]) -> list[tuple[str, int]]:
    result = []
    for name, keys in TREND_RULES.items():
        count = 0
        for paper in papers:
            text = f"{paper.title}\n{paper.summary}".lower()
            if any(key in text for key in keys):
                count += 1
        if count:
            result.append((name, count))
    result.sort(key=lambda item: item[1], reverse=True)
    return result

def infer_data_angle(paper: Paper) -> str:
    text = f"{paper.title}\n{paper.summary}".lower()
    if any(term in text for term in ["data selection", "data filtering", "data mixture"]):
        return "这篇更偏向训练前或微调前的数据筛选方法，值得关注其选择信号、验证集设计和样本效率。"
    if any(term in text for term in ["synthetic data", "generated data", "self-generated"]):
        return "这篇更偏向合成/自生成数据流程，值得关注生成质量控制、过滤策略和是否有人类或自动验证闭环。"
    if any(term in text for term in ["dataset", "benchmark", "corpus"]):
        return "这篇更偏向数据集或基准构建，值得关注数据来源、授权、规模、标注方式和污染检查。"
    if any(term in text for term in ["annotation", "labelled data", "labeled data", "pii", "privacy"]):
        return "这篇更偏向标注、隐私或安全数据，值得关注 taxonomy 设计、标注一致性和敏感数据处理边界。"
    return "这篇与 AI 数据基础设施相关，建议人工复核其数据构建、训练语料或评估语料是否可复用。"

def render_markdown(papers: list[Paper], start_date: date, end_date: date) -> str:
    week = make_week_label(end_date)
    trends = trend_counts(papers)
    lines = [
        f"# AI 数据方向周报：{week}", "",
        f"- **周期**：{start_date.isoformat()} 至 {end_date.isoformat()}",
        f"- **生成时间**：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- **论文数量**：{len(papers)}",
        "- **范围**：arXiv cs.AI、cs.CL、cs.LG、cs.CV、stat.ML 中与 AI 数据相关的近 7 天论文",
        "", "## 本周概览", "",
    ]
    if papers:
        lines += [f"本周共筛出 **{len(papers)}** 篇数据相关论文，主要集中在：" + "、".join(f"{n}（{c}）" for n, c in trends[:4]) + "。", ""]
    else:
        lines += ["本周自动抓取未筛出满足关键词阈值的论文。建议人工检查关键词或扩大检索范围。", ""]
    lines += ["## 趋势信号", ""]
    lines += [f"- **{name}**：{count} 篇相关论文。" for name, count in trends] or ["- 暂无足够样本形成趋势判断。"]
    lines += ["", "## 重点论文", ""]
    for index, paper in enumerate(papers, 1):
        authors = ", ".join(paper.authors[:6]) + (", et al." if len(paper.authors) > 6 else "")
        lines += [
            f"### {index}. {paper.title}", "",
            f"- **日期**：{paper.published.isoformat()}",
            f"- **类别**：{paper.category or 'N/A'}",
            f"- **作者**：{authors or 'N/A'}",
            f"- **关键词**：{'、'.join(paper.matched_keywords[:8]) or 'N/A'}",
            f"- **链接**：[{paper.url}]({paper.url})", "",
            "**摘要摘录**", "",
            "\n".join(textwrap.wrap(html.unescape(paper.summary), width=88)), "",
            "**数据角度初判**", "",
            infer_data_angle(paper), "",
        ]
    lines += ["## 下周跟进", "", "1. 检查高分论文是否有代码或数据集发布。", "2. 记录可复用的数据构建方法、过滤规则和评估基准。", "3. 对重复出现的主题做跨周趋势比较。", ""]
    return "\n".join(lines)

def update_index(week: str, start_date: date, end_date: date, papers: list[Paper]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    weeks = json.loads(WEEKS_JSON.read_text(encoding="utf-8")) if WEEKS_JSON.exists() else []
    entry = {
        "week": week,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "paper_count": len(papers),
        "top_titles": [paper.title for paper in papers[:3]],
        "trends": [{"name": name, "count": count} for name, count in trend_counts(papers)],
        "file": f"weekly/{week}.md",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    weeks = [item for item in weeks if item.get("week") != week]
    weeks.append(entry)
    weeks.sort(key=lambda item: item["end"], reverse=True)
    WEEKS_JSON.write_text(json.dumps(weeks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--max-results", type=int, default=250)
    args = parser.parse_args()
    end_date = date.fromisoformat(args.end_date) if args.end_date else datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=args.days - 1)
    week = make_week_label(end_date)
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    papers = filter_weekly(fetch_arxiv(args.max_results), start_date, end_date)
    (WEEKLY_DIR / f"{week}.md").write_text(render_markdown(papers, start_date, end_date), encoding="utf-8")
    update_index(week, start_date, end_date, papers)
    print(f"Generated weekly/{week}.md with {len(papers)} papers")
    return 0

if __name__ == "__main__":
    sys.exit(main())
