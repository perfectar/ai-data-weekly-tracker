#!/usr/bin/env python3
"""Build the GitHub Pages index from weekly metadata."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEEKS_JSON = ROOT / "data" / "weeks.json"
INDEX_HTML = ROOT / "index.html"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


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
              <a class="button" href="{esc(week.get("file", ""))}">查看 Markdown 周报</a>
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
      本页面由本地 AI 周报程序生成。数据索引见 <a href="data/weeks.json">data/weeks.json</a>。
    </footer>
  </div>
</body>
</html>
"""


def main() -> int:
    weeks = json.loads(WEEKS_JSON.read_text(encoding="utf-8")) if WEEKS_JSON.exists() else []
    weeks.sort(key=lambda item: item.get("end", ""), reverse=True)
    INDEX_HTML.write_text(render_index(weeks), encoding="utf-8")
    print(f"Built {INDEX_HTML.relative_to(ROOT)} with {len(weeks)} week(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
