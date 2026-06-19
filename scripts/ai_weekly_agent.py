#!/usr/bin/env python3
"""Local weekly agent: fetch papers, rebuild site, commit, and push."""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import subprocess
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EMAIL_ENV = ROOT / "config" / "email.env"


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


def commit_and_push(push: bool) -> bool:
    if not has_git_repo():
        print("No .git directory found; skip commit and push.")
        return False

    run(["git", "add", "README.md", "index.html", "data", "weekly", "scripts"])
    if not has_changes():
        print("No changes detected; skip commit.")
        return False

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run(["git", "commit", "-m", f"Update AI data weekly brief ({stamp})"])

    if push:
        if not has_remote():
            print("No origin remote configured; skip push.")
            return True
        run(["git", "push", "origin", "main"])
    return True


def load_email_env() -> dict[str, str]:
    values = dict(os.environ)
    if EMAIL_ENV.exists():
        for line in EMAIL_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def latest_week_entry() -> dict:
    weeks_path = ROOT / "data" / "weeks.json"
    if not weeks_path.exists():
        return {}
    weeks = json.loads(weeks_path.read_text(encoding="utf-8"))
    return weeks[0] if weeks else {}


def send_success_email(changed: bool) -> None:
    env = load_email_env()
    required = ["GMAIL_SMTP_USER", "GMAIL_APP_PASSWORD", "NOTICE_TO"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        print(f"Email notification skipped; missing {', '.join(missing)}.")
        return

    week = latest_week_entry()
    repo_url = env.get("REPORT_URL", "https://perfectar.github.io/ai-data-weekly-tracker/")
    week_name = week.get("week", "unknown week")
    paper_count = week.get("paper_count", "unknown")
    changed_text = "已生成并推送新的周报。" if changed else "本次运行成功，但没有检测到需要提交的新变化。"

    message = EmailMessage()
    message["From"] = env["GMAIL_SMTP_USER"]
    message["To"] = env["NOTICE_TO"]
    message["Subject"] = f"AI 数据周报任务成功：{week_name}"
    message.set_content(
        "\n".join(
            [
                "AI 数据周报定时任务已成功执行。",
                "",
                f"周次：{week_name}",
                f"周期：{week.get('start', 'N/A')} 至 {week.get('end', 'N/A')}",
                f"论文数量：{paper_count}",
                f"状态：{changed_text}",
                "",
                f"网页：{repo_url}",
                f"Markdown：{repo_url}{week.get('file', '')}",
                "",
                "这封邮件由本地 ai-data-weekly-tracker 自动发送。",
            ]
        )
    )

    host = env.get("SMTP_HOST", "smtp.gmail.com")
    port = int(env.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(env["GMAIL_SMTP_USER"], env["GMAIL_APP_PASSWORD"])
        server.send_message(message)
    print(f"Email notification sent to {env['NOTICE_TO']}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-fetch", action="store_true", help="Only rebuild site and commit existing files.")
    parser.add_argument("--no-push", action="store_true", help="Do not push to origin after committing.")
    parser.add_argument("--no-email", action="store_true", help="Do not send success email notification.")
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

    changed = commit_and_push(push=not args.no_push)
    if not args.no_email:
        send_success_email(changed=changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
