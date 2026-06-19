#!/usr/bin/env python3
"""Build the GitHub Pages index from weekly metadata."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEEKS_JSON = ROOT / "data" / "weeks.json"
INDEX_HTML = ROOT / "index.html"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def html_link_for(week: dict) -> str:
    html_file = week.get("html_file")
    if html_file:
        return str(html_file)
    markdown_file = str(week.get("file", ""))
    return markdown_file[:-3] + ".html" if markdown_file.endswith(".md") else markdown_file


def render_trends(trends: list[dict]) -> str:
    if not trends:
        return '<span class="muted">暂无趋势标签</span>'
    return "\n".join(
        f'<span class="tag">{esc(item.get("name", ""))} · {esc(item.get("count", 0))}</span>'
        for item in trends[:6]
    )


def render_titles(titles: list[str]) -> str:
    if not titles:
        return "<li>本周暂无重点论文。</li>"
    return "\n".join(f"<li>{esc(title)}</li>" for title in titles[:4])


def render_week_cards(weeks: list[dict]) -> str:
    if not weeks:
        return '<article class="empty">还没有周报。运行 <code>python3 scripts/ai_weekly_agent.py</code> 生成第一期。</article>'

    cards: list[str] = []
    for week in weeks:
        cards.append(
            f"""
            <article class="week-card">
              <div class="week-meta">
                <span>{esc(week.get("start", ""))} 至 {esc(week.get("end", ""))}</span>
                <strong>{esc(week.get("paper_count", 0))} 篇</strong>
              </div>
              <h2>{esc(week.get("week", ""))}</h2>
              <div class="tags">{render_trends(week.get("trends", []))}</div>
              <h3>优先关注</h3>
              <ol>{render_titles(week.get("top_titles", []))}</ol>
              <a class="button" href="{esc(html_link_for(week))}">查看周报</a>
            </article>
            """
        )
    return "\n".join(cards)


def render_index(weeks: list[dict]) -> str:
    latest = weeks[0] if weeks else {}
    latest_week = latest.get("week", "暂无")
    latest_count = latest.get("paper_count", 0)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI 数据前沿周报</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #d9dee8;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --soft: #eaf7f5;
      --shadow: 0 12px 28px rgba(16, 24, 40, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.6;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 1120px; margin: 0 auto; padding: 28px 18px 56px; }}
    header {{
      padding: 28px 0 24px;
      border-bottom: 1px solid var(--line);
    }}
    .eyebrow {{ color: var(--accent); font-weight: 800; font-size: 13px; letter-spacing: 0.04em; text-transform: uppercase; }}
    h1 {{ margin: 8px 0 12px; max-width: 820px; font-size: clamp(30px, 7vw, 58px); line-height: 1.08; letter-spacing: 0; }}
    .lead {{ max-width: 820px; margin: 0; color: var(--muted); font-size: 17px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 22px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      box-shadow: var(--shadow);
    }}
    .stat span {{ display: block; color: var(--muted); font-size: 13px; }}
    .stat strong {{ display: block; margin-top: 4px; font-size: 22px; }}
    .section-title {{ margin: 32px 0 14px; font-size: 22px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .week-card, .empty {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .week-meta {{ display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 13px; }}
    .week-meta strong {{ color: var(--accent-dark); }}
    h2 {{ margin: 8px 0 10px; font-size: 26px; letter-spacing: 0; }}
    h3 {{ margin: 18px 0 8px; font-size: 15px; }}
    .tags {{ display: flex; flex-wrap: wrap; gap: 8px; min-height: 32px; }}
    .tag {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      background: var(--soft);
      color: var(--accent-dark);
      padding: 5px 9px;
      font-size: 12px;
      font-weight: 700;
    }}
    ol {{ margin: 0 0 16px; padding-left: 22px; color: var(--muted); }}
    li {{ margin: 6px 0; }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 8px 13px;
      border-radius: 8px;
      background: var(--accent);
      color: #fff;
      font-weight: 750;
    }}
    .button:hover {{ background: var(--accent-dark); text-decoration: none; }}
    .muted {{ color: var(--muted); }}
    footer {{ margin-top: 34px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }}
    @media (max-width: 760px) {{
      .stats, .grid {{ grid-template-columns: 1fr; }}
      .wrap {{ padding: 22px 14px 42px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="eyebrow">AI Data Weekly Tracker</div>
      <h1>AI 数据前沿周报</h1>
      <p class="lead">每周跟踪人工智能数据方向的新论文与趋势，重点关注数据选择、合成数据、数据质量、数据治理、领域数据集、多模态语料和安全隐私数据。</p>
      <div class="stats">
        <div class="stat"><span>最新周报</span><strong>{esc(latest_week)}</strong></div>
        <div class="stat"><span>最新收录</span><strong>{esc(latest_count)} 篇</strong></div>
        <div class="stat"><span>更新时间</span><strong>{esc(updated)}</strong></div>
      </div>
    </header>

    <main>
      <h2 class="section-title">周报归档</h2>
      <div class="grid">
        {render_week_cards(weeks)}
      </div>
    </main>

    <footer>
      本页面由本地 AI 周报程序生成。数据索引见 <a href="data/weeks.json">data/weeks.json</a>，Markdown 源文件保存在 <a href="weekly/">weekly/</a>。
    </footer>
  </div>
</body>
</html>
"""


def render_inline_markdown(value: str) -> str:
    text = html.escape(value, quote=True)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: f'<a href="{match.group(2)}">{match.group(1)}</a>',
        text,
    )
    return text


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    current_list: str | None = None

    def close_list() -> None:
        nonlocal current_list
        if current_list:
            output.append(f"</{current_list}>")
            current_list = None

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{render_inline_markdown(' '.join(paragraph))}</p>")
            paragraph.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            close_list()
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            output.append(f"<h{level}>{render_inline_markdown(heading.group(2))}</h{level}>")
            continue

        unordered = re.match(r"^-\s+(.+)$", line)
        if unordered:
            flush_paragraph()
            if current_list != "ul":
                close_list()
                output.append("<ul>")
                current_list = "ul"
            output.append(f"<li>{render_inline_markdown(unordered.group(1))}</li>")
            continue

        ordered = re.match(r"^\d+\.\s+(.+)$", line)
        if ordered:
            flush_paragraph()
            if current_list != "ol":
                close_list()
                output.append("<ol>")
                current_list = "ol"
            output.append(f"<li>{render_inline_markdown(ordered.group(1))}</li>")
            continue

        close_list()
        paragraph.append(line)

    flush_paragraph()
    close_list()
    return "\n".join(output)


def extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def render_weekly_page(markdown: str, md_path: Path) -> str:
    title = extract_title(markdown, md_path.stem)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = markdown_to_html(markdown)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --paper: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #d9dee8;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --soft: #eaf7f5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.72;
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .shell {{ max-width: 920px; margin: 0 auto; padding: 22px 16px 54px; }}
    nav {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      color: var(--muted);
      font-size: 14px;
    }}
    nav .links {{ display: flex; gap: 14px; flex-wrap: wrap; }}
    article {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: clamp(20px, 5vw, 46px);
      box-shadow: 0 12px 28px rgba(16, 24, 40, 0.08);
    }}
    h1 {{
      margin: 0 0 18px;
      font-size: clamp(30px, 7vw, 52px);
      line-height: 1.12;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 34px 0 12px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      font-size: 25px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 28px 0 10px;
      font-size: 20px;
      line-height: 1.35;
      letter-spacing: 0;
    }}
    p {{ margin: 10px 0 16px; }}
    ul, ol {{ margin: 10px 0 18px; padding-left: 24px; }}
    li {{ margin: 6px 0; }}
    strong {{ color: var(--ink); }}
    code {{
      background: var(--soft);
      color: var(--accent-dark);
      border-radius: 5px;
      padding: 2px 5px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
    }}
    .generated {{
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 680px) {{
      .shell {{ padding: 16px 12px 40px; }}
      article {{ padding: 18px; }}
      nav {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <nav>
      <a href="../index.html">&larr; 返回周报首页</a>
      <div class="links">
        <a href="{esc(md_path.name)}">Markdown 源文件</a>
      </div>
    </nav>
    <article>
      {body}
      <div class="generated">网页生成时间：{esc(updated)}</div>
    </article>
  </div>
</body>
</html>
"""


def build_weekly_pages(weeks: list[dict]) -> int:
    built = 0
    for week in weeks:
        md_file = week.get("file")
        if not md_file:
            continue
        md_path = ROOT / str(md_file)
        if not md_path.exists():
            continue
        html_file = html_link_for(week)
        html_path = ROOT / html_file
        html_path.parent.mkdir(parents=True, exist_ok=True)
        markdown = md_path.read_text(encoding="utf-8")
        html_path.write_text(render_weekly_page(markdown, md_path), encoding="utf-8")
        week["html_file"] = html_file
        built += 1
    return built


def main() -> int:
    weeks = json.loads(WEEKS_JSON.read_text(encoding="utf-8")) if WEEKS_JSON.exists() else []
    weeks.sort(key=lambda item: item.get("end", ""), reverse=True)
    built = build_weekly_pages(weeks)
    WEEKS_JSON.write_text(json.dumps(weeks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    INDEX_HTML.write_text(render_index(weeks), encoding="utf-8")
    print(f"Built {INDEX_HTML.relative_to(ROOT)} with {len(weeks)} week(s) and {built} weekly HTML page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
