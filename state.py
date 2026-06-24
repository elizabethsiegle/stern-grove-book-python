import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path("entered-lotteries.json")


def load_entries() -> list[dict]:
    if not STATE_FILE.exists():
        return []
    return json.loads(STATE_FILE.read_text())


def save_entry(entry: dict) -> None:
    entries = load_entries()
    entries.append(entry)
    STATE_FILE.write_text(json.dumps(entries, indent=2))


def push_state(artist: str, show_date: str) -> None:
    token = os.environ.get("GIT_TOKEN", "")
    repo = os.environ.get("GIT_REPO", "")
    remote = f"https://x-access-token:{token}@github.com/{repo}.git"
    commit_msg = f"chore: record lottery entry for {artist} {show_date}"
    try:
        subprocess.run(["git", "config", "user.email", "action@github.com"], check=True)
        subprocess.run(["git", "config", "user.name", "GitHub Actions"], check=True)
        subprocess.run(["git", "add", "entered-lotteries.json"], check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push", remote, "HEAD:main"], check=True)
    except Exception:
        logger.error("[state] git push failed (entry still recorded locally)", exc_info=False)
