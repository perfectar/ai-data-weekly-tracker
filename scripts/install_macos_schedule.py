#!/usr/bin/env python3
"""Install a macOS LaunchAgent that runs the local weekly AI data agent every Sunday."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.codex.ai-data-weekly-tracker"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = ROOT / "logs"


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    plist = {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(ROOT / "scripts" / "ai_weekly_agent.py"),
        ],
        "WorkingDirectory": str(ROOT),
        "StartCalendarInterval": {
            "Weekday": 0,
            "Hour": 10,
            "Minute": 0,
        },
        "StandardOutPath": str(LOG_DIR / "weekly-agent.out.log"),
        "StandardErrorPath": str(LOG_DIR / "weekly-agent.err.log"),
        "RunAtLoad": False,
    }

    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist, handle)

    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)], check=True)
    subprocess.run(["launchctl", "enable", f"gui/{uid}/{LABEL}"], check=False)

    print(f"Installed {PLIST_PATH}")
    print("Schedule: every Sunday at 10:00 local time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
