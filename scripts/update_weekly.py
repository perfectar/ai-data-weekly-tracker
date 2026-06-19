#!/usr/bin/env python3
"""Fetch recent AI data papers from arXiv and build a weekly Markdown brief."""

from __future__ import annotations

import argparse
import difflib
import html
import json
import os
import re
import socket
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
OPENALEX_API = "https://api.openalex.org/works"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

CATEGORY_QUERY = "(cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:cs.CV OR cat:stat.ML)"

KEYWORDS = {
    "data selection": 5,
    "data curation": 5,
    "data quality": 5,
    "dataset": 4,
    "benchmark": 3,
    "synthetic data": 5,
    "generated data": 4,
    "training data": 5,
    "pretraining data": 5,
    "post-training data": 5,
    "instruction data": 5,
    "data mixture": 4,
    "data filtering": 5,
    "data governance": 5,
    "data lineage": 5,
    "data contamination": 5,
    "annotation": 4,
    "labelled data": 4,
    "labeled data": 4,
    "data scarcity": 4,
    "corpus": 4,
    "multilingual data": 4,
    "tabular data": 4,
    "privacy": 3,
    "pii": 5,
    "bias dataset": 4,
    "tool-calling dataset": 5,
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
    author_affiliations: list[str]
    summary: str
    url: str
    published: date
    category: str
    score: int
    matched_keywords: list[str]


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_arxiv_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def score_paper(title: str, summary: str) -> tuple[int, list[str]]:
    haystack = f"{title}\n{summary}".lower()
    matches: list[str] = []
    score = 0
    for keyword, weight in KEYWORDS.items():
        if keyword in haystack:
            matches.append(keyword)
            score += weight
    return score, matches


def fetch_arxiv(max_results: int = 200, retries: int = 3) -> list[Paper]:
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
                xml_bytes = response.read()
            root = ET.fromstring(xml_bytes)
            papers: list[Paper] = []
            for entry in root.findall("atom:entry", ARXIV_NS):
                title = clean_text(entry.findtext("atom:title", default="", namespaces=ARXIV_NS))
                summary = clean_text(entry.findtext("atom:summary", default="", namespaces=ARXIV_NS))
                published_raw = entry.findtext("atom:published", default="", namespaces=ARXIV_NS)
                if not title or not summary or not published_raw:
                    continue

                authors: list[str] = []
                author_affiliations: list[str] = []
                for node in entry.findall("atom:author", ARXIV_NS):
                    author = clean_text(node.findtext("atom:name", default="", namespaces=ARXIV_NS))
                    if not author:
                        continue
                    authors.append(author)
                    author_affiliations.append(
                        clean_text(node.findtext("arxiv:affiliation", default="", namespaces=ARXIV_NS))
                    )

                arxiv_id = clean_text(entry.findtext("atom:id", default="", namespaces=ARXIV_NS))
                primary_category = entry.find("arxiv:primary_category", ARXIV_NS)
                category = primary_category.attrib.get("term", "") if primary_category is not None else ""
                score, matched_keywords = score_paper(title, summary)

                papers.append(
                    Paper(
                        title=title,
                        authors=authors,
                        author_affiliations=author_affiliations,
                        summary=summary,
                        url=arxiv_id,
                        published=parse_arxiv_date(published_raw),
                        category=category,
                        score=score,
                        matched_keywords=matched_keywords,
                    )
                )
            return papers
        except Exception as exc:  # pragma: no cover - exercised in CI/network failures
            last_error = exc
            time.sleep(2 + attempt * 2)

    raise RuntimeError(f"Failed to fetch arXiv feed: {last_error}")


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def fetch_openalex_work(title: str, retries: int = 1, timeout: int = 8) -> dict | None:
    params = {"search": title, "per-page": 1}
    mailto = os.environ.get("OPENALEX_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto
    url = f"{OPENALEX_API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "ai-data-weekly-tracker/1.0"})

    for attempt in range(retries):
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = payload.get("results", [])
            if not results:
                return None
            work = results[0]
            result_title = work.get("title") or work.get("display_name") or ""
            similarity = difflib.SequenceMatcher(None, normalize_title(title), normalize_title(result_title)).ratio()
            return work if similarity >= 0.82 else None
        except Exception:
            time.sleep(1 + attempt)
        finally:
            socket.setdefaulttimeout(previous_timeout)
    return None


def openalex_affiliation_from_authorship(authorship: dict) -> str:
    raw_affiliations = [
        clean_text(value)
        for value in authorship.get("raw_affiliation_strings", [])
        if clean_text(value)
    ]
    if raw_affiliations:
        return "；".join(dict.fromkeys(raw_affiliations))

    institutions = [
        clean_text(institution.get("display_name", ""))
        for institution in authorship.get("institutions", [])
        if clean_text(institution.get("display_name", ""))
    ]
    return "；".join(dict.fromkeys(institutions))


def augment_affiliations_from_openalex(papers: list[Paper]) -> None:
    for paper in papers:
        if any(affiliation.strip() for affiliation in paper.author_affiliations):
            continue
        work = fetch_openalex_work(paper.title)
        if not work:
            continue

        affiliations = [
            openalex_affiliation_from_authorship(authorship)
            for authorship in work.get("authorships", [])
        ]
        affiliations = affiliations[: len(paper.authors)]
        if any(affiliation.strip() for affiliation in affiliations):
            paper.author_affiliations = affiliations
        time.sleep(0.1)


def filter_weekly(papers: list[Paper], start_date: date, end_date: date) -> list[Paper]:
    seen: set[str] = set()
    selected: list[Paper] = []
    for paper in papers:
        if paper.url in seen:
            continue
        seen.add(paper.url)
        if start_date <= paper.published <= end_date and paper.score >= 4:
            selected.append(paper)

    selected.sort(key=lambda item: (item.score, item.published), reverse=True)
    return selected[:20]


def trend_counts(papers: list[Paper]) -> list[tuple[str, int]]:
    counts: list[tuple[str, int]] = []
    for trend, keywords in TREND_RULES.items():
        total = 0
        for paper in papers:
            haystack = f"{paper.title}\n{paper.summary}".lower()
            if any(keyword in haystack for keyword in keywords):
                total += 1
        if total:
            counts.append((trend, total))
    counts.sort(key=lambda item: item[1], reverse=True)
    return counts


def wrap_summary(summary: str, width: int = 88) -> str:
    escaped = html.unescape(summary)
    return "\n".join(textwrap.wrap(escaped, width=width))


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def make_week_label(end_date: date) -> str:
    iso_year, iso_week, _ = end_date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def render_markdown(papers: list[Paper], start_date: date, end_date: date) -> str:
    week_label = make_week_label(end_date)
    trends = trend_counts(papers)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        f"# AI 数据方向周报：{week_label}",
        "",
        f"- **周期**：{start_date.isoformat()} 至 {end_date.isoformat()}",
        f"- **生成时间**：{generated_at}",
        f"- **论文数量**：{len(papers)}",
        "- **范围**：arXiv cs.AI、cs.CL、cs.LG、cs.CV、stat.ML 中与 AI 数据相关的近 7 天论文",
        "",
        "## 本周概览",
        "",
    ]

    if papers:
        top_trends = "、".join(f"{name}（{count}）" for name, count in trends[:4]) or "数据集与训练数据"
        top_titles = "；".join(paper.title for paper in papers[:3])
        lines.extend(
            [
                f"本周共筛出 **{len(papers)}** 篇数据相关论文，主要集中在：{top_trends}。",
                "",
                f"优先关注前三篇：{top_titles}。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "本周自动抓取未筛出满足关键词阈值的论文。建议人工检查 arXiv 搜索条件，或在 `scripts/update_weekly.py` 中补充关键词。",
                "",
            ]
        )

    lines.extend(["## 趋势信号", ""])
    if trends:
        for trend, count in trends:
            lines.append(f"- **{trend}**：{count} 篇相关论文。")
    else:
        lines.append("- 暂无足够样本形成趋势判断。")

    lines.extend(["", "## 重点论文", ""])
    for index, paper in enumerate(papers, start=1):
        authors = ", ".join(paper.authors[:6])
        if len(paper.authors) > 6:
            authors += ", et al."
        keyword_text = "、".join(paper.matched_keywords[:8])
        lines.extend(
            [
                f"### {index}. {paper.title}",
                "",
                f"- **日期**：{paper.published.isoformat()}",
                f"- **类别**：{paper.category or 'N/A'}",
                f"- **作者**：{authors or 'N/A'}",
                f"- **作者单位**：{format_author_affiliations(paper)}",
                f"- **关键词**：{keyword_text or 'N/A'}",
                f"- **链接**：[{paper.url}]({paper.url})",
                "",
                "**摘要摘录**",
                "",
                wrap_summary(paper.summary),
                "",
                "**数据角度初判**",
                "",
                infer_data_angle(paper),
                "",
                "**中文解读与航空 AI 数据启示**",
                "",
                infer_chinese_reading(paper),
                "",
            ]
        )

    lines.extend(
        [
            "## 下周跟进",
            "",
            "1. 检查高分论文是否有代码或数据集发布。",
            "2. 记录可复用的数据构建方法、过滤规则和评估基准。",
            "3. 对重复出现的主题做跨周趋势比较。",
            "",
        ]
    )

    return "\n".join(lines)


def infer_data_angle(paper: Paper) -> str:
    haystack = f"{paper.title}\n{paper.summary}".lower()
    if has_any(haystack, ["data selection", "data filtering", "data mixture"]):
        return "这篇更偏向训练前或微调前的数据筛选方法，值得关注其选择信号、验证集设计和样本效率。"
    if has_any(haystack, ["synthetic data", "generated data", "self-generated"]):
        return "这篇更偏向合成/自生成数据流程，值得关注生成质量控制、过滤策略和是否有人类或自动验证闭环。"
    if has_any(haystack, ["dataset", "benchmark", "corpus"]):
        return "这篇更偏向数据集或基准构建，值得关注数据来源、授权、规模、标注方式和污染检查。"
    if has_any(haystack, ["annotation", "labelled data", "labeled data", "pii", "privacy"]):
        return "这篇更偏向标注、隐私或安全数据，值得关注 taxonomy 设计、标注一致性和敏感数据处理边界。"
    return "这篇与 AI 数据基础设施相关，建议人工复核其数据构建、训练语料或评估语料是否可复用。"


def format_author_affiliations(paper: Paper) -> str:
    pairs = [
        (author, paper.author_affiliations[index].strip())
        for index, author in enumerate(paper.authors)
        if index < len(paper.author_affiliations) and paper.author_affiliations[index].strip()
    ]
    if not pairs:
        return "arXiv 未提供作者单位；建议查看论文 PDF 首页或项目页确认高校/实验室。"

    shown = "；".join(f"{author}（{affiliation}）" for author, affiliation in pairs[:6])
    if len(pairs) < len(paper.authors):
        shown += "；其余作者 arXiv 未提供单位"
    elif len(pairs) > 6:
        shown += "；等"
    return shown


def infer_research_logic(paper: Paper) -> str:
    haystack = f"{paper.title}\n{paper.summary}".lower()
    if has_any(haystack, ["retrieval", "rag", "question answering", "long-context", "extraction"]):
        return "论文的核心逻辑是把非结构化知识或长文档转化为可检索、可引用、可评测的问答/抽取任务，用数据组织和证据约束提升模型回答的可靠性。"
    if has_any(haystack, ["data selection", "data filtering", "data mixture", "curation"]):
        return "论文的核心逻辑是先定义样本价值信号，再用过滤、配比或质量评估方法组织训练数据，目标是在更少或更干净的数据上获得更稳定的模型效果。"
    if has_any(haystack, ["synthetic data", "generated data", "self-generated"]):
        return "论文的核心逻辑是用模型或程序化流程生成补充数据，再通过筛选、验证或评测闭环控制噪声，缓解真实标注数据不足的问题。"
    if has_any(haystack, ["benchmark", "evaluation", "leaderboard"]):
        return "论文的核心逻辑是构造可复现实验基准，把任务、数据、指标和错误类型固定下来，用统一评测暴露模型在真实场景中的能力边界。"
    if has_any(haystack, ["dataset", "corpus", "annotation", "labelled data", "labeled data"]):
        return "论文的核心逻辑是围绕特定任务构建数据集或语料，重点在数据来源、标注规范、样本覆盖和任务定义上形成可复用的数据资产。"
    if has_any(haystack, ["privacy", "pii", "contamination", "bias", "safety"]):
        return "论文的核心逻辑是识别数据使用中的隐私、污染、偏差或安全风险，并通过检测、约束或评估机制降低模型训练和部署的不确定性。"
    if has_any(haystack, ["multimodal", "image", "video", "vision", "audio", "speech", "tabular"]):
        return "论文的核心逻辑是把文本之外的图像、视频、语音或表格数据组织成可训练/可评测样本，使模型能够处理更接近真实业务流程的多源信息。"
    return "论文的核心逻辑是围绕一个具体 AI 任务梳理数据、模型与评测之间的关系，值得重点看其数据定义、实验设置和误差分析是否可迁移。"


def infer_research_highlight(paper: Paper) -> str:
    haystack = f"{paper.title}\n{paper.summary}".lower()
    highlights: list[str] = []
    if has_any(haystack, ["low-resource", "low resources", "scarcity", "rare"]):
        highlights.append("低资源或稀缺场景下的数据构建思路")
    if has_any(haystack, ["synthetic data", "generated data", "self-generated"]):
        highlights.append("合成数据与质量控制闭环")
    if has_any(haystack, ["benchmark", "evaluation"]):
        highlights.append("可复现的评测任务和指标设计")
    if has_any(haystack, ["retrieval", "rag", "grounded", "long-context", "extraction"]):
        highlights.append("基于证据的检索、长上下文或抽取能力")
    if has_any(haystack, ["annotation", "taxonomy", "label"]):
        highlights.append("标注体系和标签定义")
    if has_any(haystack, ["privacy", "pii", "contamination", "bias", "safety"]):
        highlights.append("数据安全、隐私或污染控制")
    if has_any(haystack, ["multimodal", "image", "video", "audio", "speech", "tabular"]):
        highlights.append("多模态或结构化数据组织方式")
    if not highlights:
        highlights.append("任务数据化、评测标准化和误差分析方法")
    return "亮点在于：" + "；".join(highlights[:3]) + "。"


def infer_aviation_reference(paper: Paper) -> str:
    haystack = f"{paper.title}\n{paper.summary}".lower()
    if has_any(haystack, ["retrieval", "rag", "question answering", "long-context", "extraction"]):
        return "对航空 AI 数据的借鉴是：可把维修手册、适航条款、运行通告、飞行报告和故障记录整理成带证据链的问答/抽取数据，用于训练面向工程师和运行人员的可追溯助手。"
    if has_any(haystack, ["synthetic data", "generated data", "self-generated"]):
        return "对航空 AI 数据的借鉴是：可用合成数据补足小概率故障、极端天气、复杂机场场景和罕见告警样本，但必须配套专家审核、仿真一致性检查和风险分级过滤。"
    if has_any(haystack, ["data selection", "data filtering", "data mixture", "curation"]):
        return "对航空 AI 数据的借鉴是：可建立飞行阶段、机型、机场、气象、故障类型和传感器质量等维度的样本选择规则，避免训练集被高频普通航段淹没。"
    if has_any(haystack, ["benchmark", "evaluation", "leaderboard"]):
        return "对航空 AI 数据的借鉴是：可沉淀航空专用基准集，例如维修诊断、航班运行风险识别、签派决策解释、运行文档问答和多源告警归因，形成跨模型可比较的评测体系。"
    if has_any(haystack, ["annotation", "labelled data", "labeled data", "taxonomy", "corpus", "dataset"]):
        return "对航空 AI 数据的借鉴是：可把航空事件、维修缺陷、部件更换、飞行阶段、管制意图和安全风险建立统一标签体系，并记录标注依据与复核流程。"
    if has_any(haystack, ["privacy", "pii", "contamination", "bias", "safety"]):
        return "对航空 AI 数据的借鉴是：可把航司、旅客、机组和运行安全相关字段纳入脱敏、权限、污染检测和偏差审计流程，降低数据进入模型后的合规与安全风险。"
    if has_any(haystack, ["multimodal", "image", "video", "vision", "audio", "speech", "tabular"]):
        return "对航空 AI 数据的借鉴是：可把机载参数、维修图片、机场视频、语音通话、气象报文和运行表格对齐到同一事件时间线，支持多模态诊断和态势理解。"
    return "对航空 AI 数据的借鉴是：优先复用其数据定义、样本组织和评测方式，并映射到航空中的安全事件、运行效率、维修保障和知识问答场景。"


def infer_chinese_reading(paper: Paper) -> str:
    return "\n".join(
        [
            f"- **核心逻辑**：{infer_research_logic(paper)}",
            f"- **主要亮点**：{infer_research_highlight(paper)}",
            f"- **航空 AI 数据参考**：{infer_aviation_reference(paper)}",
        ]
    )


def update_weeks_index(week_label: str, start_date: date, end_date: date, papers: list[Paper]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if WEEKS_JSON.exists():
        weeks = json.loads(WEEKS_JSON.read_text(encoding="utf-8"))
    else:
        weeks = []

    entry = {
        "week": week_label,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "paper_count": len(papers),
        "top_titles": [paper.title for paper in papers[:3]],
        "trends": [{"name": name, "count": count} for name, count in trend_counts(papers)],
        "file": f"weekly/{week_label}.md",
        "html_file": f"weekly/{week_label}.html",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    weeks = [item for item in weeks if item.get("week") != week_label]
    weeks.append(entry)
    weeks.sort(key=lambda item: item["end"], reverse=True)
    WEEKS_JSON.write_text(json.dumps(weeks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD. Defaults to today UTC.")
    parser.add_argument("--days", type=int, default=7, help="Number of days in the weekly window.")
    parser.add_argument("--max-results", type=int, default=250, help="Number of recent arXiv entries to fetch.")
    parser.add_argument(
        "--no-affiliation-lookup",
        action="store_true",
        help="Skip OpenAlex affiliation lookup and only use arXiv metadata.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    end_date = date.fromisoformat(args.end_date) if args.end_date else datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=args.days - 1)
    week_label = make_week_label(end_date)

    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    papers = filter_weekly(fetch_arxiv(max_results=args.max_results), start_date, end_date)
    if not args.no_affiliation_lookup:
        augment_affiliations_from_openalex(papers)
    markdown = render_markdown(papers, start_date, end_date)
    (WEEKLY_DIR / f"{week_label}.md").write_text(markdown, encoding="utf-8")
    update_weeks_index(week_label, start_date, end_date, papers)

    print(f"Generated weekly/{week_label}.md with {len(papers)} papers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
