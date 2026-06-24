# Stern Grove Lottery Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daily GitHub Actions cron that detects open Stern Grove Festival lottery windows and submits a form entry via Playwright, tracking state in a committed JSON file and notifying via Resend email.

**Architecture:** A Python orchestrator (`lottery.py`) calls three focused modules: `state.py` for JSON state + git push, `browser.py` for all Playwright interactions (concert discovery + form filling + CAPTCHA bypass), and `notify.py` for Resend emails. GitHub Actions runs the script on a daily cron at 10:05am PT.

**Tech Stack:** Python 3.12, Playwright 1.44 (async API, Chromium), Resend Python SDK 2.3, python-dotenv 1.0.1, pytest + pytest-asyncio + pytest-mock

## Global Constraints

- Python 3.12
- Exact pinned versions: `playwright==1.44.0`, `python-dotenv==1.0.1`, `resend==2.3.0`
- All personal data loaded from environment variables — never hardcoded
- Only one lottery entry per run (enforced by state check at startup)
- `entered-lotteries.json` committed back to the repo via `GIT_TOKEN` PAT after every successful entry
- Resend errors and git push errors are logged but never re-raised
- Headless Chromium only (Browserbase is available but unused)
- Cron schedule: `5 17 * * *` (10:05am PDT = 17:05 UTC, summer only)

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `entered-lotteries.json`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Modify: `.gitignore` (append)

**Interfaces:**
- Produces: installable Python environment; empty state file; test runner configured for async

- [ ] **Step 1: Create `requirements.txt`**

```
playwright==1.44.0
python-dotenv==1.0.1
resend==2.3.0
pytest==8.2.0
pytest-asyncio==0.23.7
pytest-mock==3.14.0
```

- [ ] **Step 2: Create empty state file `entered-lotteries.json`**

```json
[]
```

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 4: Create test package**

```bash
mkdir -p tests && touch tests/__init__.py
```

- [ ] **Step 5: Append to `.gitignore`** (create if absent)

```
.env
__pycache__/
.pytest_cache/
*.pyc
```

- [ ] **Step 6: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium --with-deps
```

Expected: no errors; `playwright --version` prints a version string.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt entered-lotteries.json pytest.ini tests/__init__.py .gitignore
git commit -m "chore: project scaffolding"
```

---

### Task 2: State management (`state.py`)

**Files:**
- Create: `state.py`
- Create: `tests/test_state.py`

**Interfaces:**
- Produces:
  - `load_entries() -> list[dict]` — reads `entered-lotteries.json`; returns `[]` if the file is missing
  - `save_entry(entry: dict) -> None` — appends one entry to the file and writes it back

- [ ] **Step 1: Write failing tests — create `tests/test_state.py`**

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_load_entries_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from state import load_entries
    assert load_entries() == []


def test_load_entries_empty_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "entered-lotteries.json").write_text("[]")
    from state import load_entries
    assert load_entries() == []


def test_load_entries_populated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = [{"concert_id": 6, "event_id": "11997", "artist": "Test", "show_date": "2026-07-12", "entered_at": "2026-06-14T10:07:23Z", "status": "submitted"}]
    (tmp_path / "entered-lotteries.json").write_text(json.dumps(data))
    from state import load_entries
    assert load_entries() == data


def test_save_entry_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entry = {"concert_id": 7, "event_id": "12000", "artist": "New Artist", "show_date": "2026-07-19", "entered_at": "2026-06-21T10:08:00Z", "status": "submitted"}
    from state import save_entry
    save_entry(entry)
    data = json.loads((tmp_path / "entered-lotteries.json").read_text())
    assert data == [entry]


def test_save_entry_appends_to_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    existing = [{"concert_id": 6, "event_id": "11997", "artist": "Old", "show_date": "2026-07-12", "entered_at": "2026-06-14T10:07:23Z", "status": "submitted"}]
    (tmp_path / "entered-lotteries.json").write_text(json.dumps(existing))
    new_entry = {"concert_id": 7, "event_id": "12000", "artist": "New", "show_date": "2026-07-19", "entered_at": "2026-06-21T10:07:00Z", "status": "submitted"}
    from state import save_entry
    save_entry(new_entry)
    data = json.loads((tmp_path / "entered-lotteries.json").read_text())
    assert len(data) == 2
    assert data[-1] == new_entry


def test_push_state_does_not_raise_on_git_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_TOKEN", "fake_token")
    monkeypatch.setenv("GIT_REPO", "owner/repo")
    (tmp_path / "entered-lotteries.json").write_text("[]")
    with patch("subprocess.run", side_effect=Exception("git error")):
        from state import push_state
        push_state("The Roots", "2026-07-12")  # must not raise


def test_push_state_uses_token_in_remote_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_TOKEN", "mytoken123")
    monkeypatch.setenv("GIT_REPO", "lizzie/stern-grove")
    (tmp_path / "entered-lotteries.json").write_text("[]")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        from state import push_state
        push_state("The Roots", "2026-07-12")
    all_args = " ".join(str(c) for c in mock_run.call_args_list)
    assert "mytoken123" in all_args
    assert "lizzie/stern-grove" in all_args
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'state'`

- [ ] **Step 3: Implement `state.py`**

```python
import json
import os
import subprocess
from pathlib import Path

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
    except Exception as exc:
        print(f"[state] git push failed (entry still recorded locally): {exc}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_state.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add state.py tests/test_state.py
git commit -m "feat: state management — load/save entered-lotteries.json and git push"
```

---

### Task 3: Resend notifications (`notify.py`)

**Files:**
- Create: `notify.py`
- Create: `tests/test_notify.py`

**Interfaces:**
- Consumes: env vars `RESEND_API_KEY`, `RESEND_FROM`, `NOTIFY_EMAIL`
- Produces:
  - `send_success(concert: dict) -> None` — concert has keys `artist`, `show_date`, optionally `entered_at`
  - `send_failure(concert: dict, error_text: str) -> None`
  - Both functions catch and log any Resend exception without re-raising

- [ ] **Step 1: Write failing tests — create `tests/test_notify.py`**

```python
import pytest
from unittest.mock import patch, MagicMock

CONCERT = {
    "concert_id": 6,
    "event_id": "11997",
    "artist": "The Roots",
    "show_date": "2026-07-12",
    "entered_at": "2026-06-17T10:05:00Z",
}


def test_send_success_subject_and_recipients(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("RESEND_FROM", "from@test.com")
    monkeypatch.setenv("NOTIFY_EMAIL", "to@test.com")
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send):
        from notify import send_success
        send_success(CONCERT)
    payload = mock_send.call_args[0][0]
    assert "The Roots" in payload["subject"]
    assert "2026-07-12" in payload["subject"]
    assert payload["from"] == "from@test.com"
    assert payload["to"] == ["to@test.com"]
    assert "4" in payload["text"]


def test_send_failure_subject_contains_failed(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("RESEND_FROM", "from@test.com")
    monkeypatch.setenv("NOTIFY_EMAIL", "to@test.com")
    mock_send = MagicMock()
    with patch("resend.Emails.send", mock_send):
        from notify import send_failure
        send_failure(CONCERT, "TimeoutError: selector not found after 15s")
    payload = mock_send.call_args[0][0]
    assert "FAILED" in payload["subject"]
    assert "TimeoutError" in payload["text"]


def test_send_success_does_not_raise_on_resend_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("RESEND_FROM", "from@test.com")
    monkeypatch.setenv("NOTIFY_EMAIL", "to@test.com")
    with patch("resend.Emails.send", side_effect=Exception("API down")):
        from notify import send_success
        send_success(CONCERT)  # must not raise


def test_send_failure_does_not_raise_on_resend_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("RESEND_FROM", "from@test.com")
    monkeypatch.setenv("NOTIFY_EMAIL", "to@test.com")
    with patch("resend.Emails.send", side_effect=Exception("API down")):
        from notify import send_failure
        send_failure(CONCERT, "some error")  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_notify.py -v
```

Expected: `ModuleNotFoundError: No module named 'notify'`

- [ ] **Step 3: Implement `notify.py`**

```python
import os
import resend


def send_success(concert: dict) -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]
    try:
        resend.Emails.send({
            "from": os.environ["RESEND_FROM"],
            "to": [os.environ["NOTIFY_EMAIL"]],
            "subject": f"Stern Grove lottery entered — {concert['artist']} ({concert['show_date']})",
            "text": (
                f"Artist: {concert['artist']}\n"
                f"Show date: {concert['show_date']}\n"
                f"Tickets requested: 4\n"
                f"Entered at: {concert.get('entered_at', 'unknown')}"
            ),
        })
    except Exception as exc:
        print(f"[notify] Resend error (success email): {exc}")


def send_failure(concert: dict, error_text: str) -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]
    try:
        resend.Emails.send({
            "from": os.environ["RESEND_FROM"],
            "to": [os.environ["NOTIFY_EMAIL"]],
            "subject": f"Stern Grove lottery FAILED — {concert['artist']} ({concert['show_date']})",
            "text": f"Error:\n\n{error_text}",
        })
    except Exception as exc:
        print(f"[notify] Resend error (failure email): {exc}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_notify.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add notify.py tests/test_notify.py
git commit -m "feat: Resend success/failure email notifications"
```

---

### Task 4: Inspect `window.TixologiWidget.concerts` schema

**Files:**
- Create: `inspect_widget.py` (temporary — deleted after running)

**Interfaces:**
- Produces: knowledge of exact field names in the TixologiWidget concerts object, required for Task 5

This task has no unit tests — it is a one-off live inspection.

- [ ] **Step 1: Create `inspect_widget.py`**

```python
import asyncio
import json
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.sterngrove.org/lineup2026", wait_until="networkidle", timeout=30000)
        result = await page.evaluate("""() => {
            if (!window.TixologiWidget) return {error: 'TixologiWidget not found'};
            return window.TixologiWidget.concerts;
        }""")
        print(json.dumps(result, indent=2, default=str))
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Run the inspector and record the output**

```bash
python inspect_widget.py 2>&1
```

Expected: JSON showing all concerts. For each concert object, note:
- The field that holds the integer concert ID (matches `data-sgf-concert` attribute — e.g., `6`)
- The field that holds the Tixologi event ID (matches `data-tixologi-event-id` — e.g., `"11997"`)
- The field(s) indicating whether the lottery window is open (likely a boolean flag or ISO datetime pair)
- The field holding the artist name
- The field holding the show date

Record these field names — you will substitute them into Task 5 step 3.

- [ ] **Step 3: Delete the inspector script**

```bash
rm inspect_widget.py
```

- [ ] **Step 4: Commit with schema documented**

```bash
git commit --allow-empty -m "chore: TixologiWidget.concerts schema documented

Fields observed from live inspection:
- Concert ID field: <insert>
- Tixologi event ID field: <insert>
- Lottery open field: <insert>
- Lottery close field: <insert>
- Artist name field: <insert>
- Show date field: <insert>"
```

---

### Task 5: Concert discovery (`browser.py` — discovery functions)

**Files:**
- Create: `browser.py`
- Create: `tests/test_browser.py`

**Interfaces:**
- Consumes: `entries: list[dict]` (output of `load_entries()` from `state.py`)
- Produces:
  - `_is_lottery_open(concert: dict, now: datetime) -> bool`
  - `_is_already_entered(concert: dict, entries: list[dict]) -> bool`
  - `_concert_to_entry_shape(concert: dict) -> dict` — returns `{concert_id, event_id, artist, show_date}`
  - `async find_open_lottery(entries: list[dict]) -> dict | None`

**Before writing code:** substitute the real field names from Task 4 for every occurrence of `lotteryOpen`, `lotteryClose`, `tixologiEventId`, `artist`, `date`, and `id` in the code below if they differ.

- [ ] **Step 1: Write failing tests — create `tests/test_browser.py`**

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch


OPEN_TS = "2026-06-14T10:00:00"
CLOSE_TS = "2026-06-21T10:00:00"
PAST_CLOSE_TS = "2026-06-10T10:00:00"

# Replace field names below with actual names from Task 4 if different
CONCERT_RAW = {
    "id": 6,
    "tixologiEventId": "11997",
    "artist": "The Roots",
    "date": "2026-07-12",
    "lotteryOpen": OPEN_TS,
    "lotteryClose": CLOSE_TS,
}


def test_is_lottery_open_within_window():
    from browser import _is_lottery_open
    now = datetime(2026, 6, 17, 10, 5, tzinfo=timezone.utc)
    assert _is_lottery_open(CONCERT_RAW, now) is True


def test_is_lottery_open_before_window():
    from browser import _is_lottery_open
    now = datetime(2026, 6, 13, 9, 59, tzinfo=timezone.utc)
    assert _is_lottery_open(CONCERT_RAW, now) is False


def test_is_lottery_open_after_window():
    from browser import _is_lottery_open
    closed = dict(CONCERT_RAW, lotteryClose=PAST_CLOSE_TS)
    now = datetime(2026, 6, 17, 10, 5, tzinfo=timezone.utc)
    assert _is_lottery_open(closed, now) is False


def test_is_already_entered_true():
    from browser import _is_already_entered
    entries = [{"concert_id": 6}]
    assert _is_already_entered(CONCERT_RAW, entries) is True


def test_is_already_entered_false():
    from browser import _is_already_entered
    entries = [{"concert_id": 5}]
    assert _is_already_entered(CONCERT_RAW, entries) is False


def test_concert_to_entry_shape():
    from browser import _concert_to_entry_shape
    result = _concert_to_entry_shape(CONCERT_RAW)
    assert result == {
        "concert_id": 6,
        "event_id": "11997",
        "artist": "The Roots",
        "show_date": "2026-07-12",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_browser.py -v
```

Expected: `ModuleNotFoundError: No module named 'browser'`

- [ ] **Step 3: Implement discovery functions in `browser.py`**

Substitute actual field names from Task 4 where indicated.

```python
from datetime import datetime, timezone
from playwright.async_api import async_playwright


# --- field name constants (update from Task 4 inspection) ---
FIELD_ID = "id"
FIELD_EVENT_ID = "tixologiEventId"
FIELD_ARTIST = "artist"
FIELD_SHOW_DATE = "date"
FIELD_LOTTERY_OPEN = "lotteryOpen"
FIELD_LOTTERY_CLOSE = "lotteryClose"
# -----------------------------------------------------------


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_lottery_open(concert: dict, now: datetime) -> bool:
    open_dt = _parse_dt(concert[FIELD_LOTTERY_OPEN])
    close_dt = _parse_dt(concert[FIELD_LOTTERY_CLOSE])
    return open_dt <= now <= close_dt


def _is_already_entered(concert: dict, entries: list[dict]) -> bool:
    return any(e["concert_id"] == concert[FIELD_ID] for e in entries)


def _concert_to_entry_shape(concert: dict) -> dict:
    return {
        "concert_id": concert[FIELD_ID],
        "event_id": str(concert[FIELD_EVENT_ID]),
        "artist": concert[FIELD_ARTIST],
        "show_date": concert[FIELD_SHOW_DATE],
    }


async def find_open_lottery(entries: list[dict]) -> dict | None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(
            "https://www.sterngrove.org/lineup2026",
            wait_until="networkidle",
            timeout=30000,
        )
        concerts = await page.evaluate("() => window.TixologiWidget.concerts")
        await browser.close()

    if isinstance(concerts, dict):
        concerts = list(concerts.values())

    now = datetime.now(timezone.utc)
    for concert in concerts:
        if _is_lottery_open(concert, now) and not _is_already_entered(concert, entries):
            return _concert_to_entry_shape(concert)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_browser.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add browser.py tests/test_browser.py
git commit -m "feat: concert discovery via window.TixologiWidget.concerts"
```

---

### Task 6: Form filling + CAPTCHA bypass (`browser.py` — form functions)

**Files:**
- Modify: `browser.py` (append `_handle_captcha` and `enter_lottery`)
- Modify: `tests/test_browser.py` (append form tests)

**Interfaces:**
- Consumes: `concert: dict` with keys `concert_id`, `event_id`, `artist`, `show_date`; env vars `FIRST_NAME`, `LAST_NAME`, `EMAIL`, `ZIP_CODE`, `GENDER`, `AGE`, `ETHNICITY`, `ANNUAL_HOUSEHOLD_INCOME`
- Produces: `async enter_lottery(concert: dict) -> None` — raises on failure (page timeout, missing field, no success element)

- [ ] **Step 1: Append failing test to `tests/test_browser.py`**

```python
import os
from unittest.mock import AsyncMock, patch


def test_enter_lottery_registers_captcha_route_and_navigates(monkeypatch):
    monkeypatch.setenv("FIRST_NAME", "Lizzie")
    monkeypatch.setenv("LAST_NAME", "Siegle")
    monkeypatch.setenv("EMAIL", "test@test.com")
    monkeypatch.setenv("ZIP_CODE", "94108")
    monkeypatch.setenv("GENDER", "female")
    monkeypatch.setenv("AGE", "25-34")
    monkeypatch.setenv("ETHNICITY", "mixed")
    monkeypatch.setenv("ANNUAL_HOUSEHOLD_INCOME", "200k-500k")

    page_mock = AsyncMock()
    browser_mock = AsyncMock()
    browser_mock.new_page = AsyncMock(return_value=page_mock)
    playwright_mock = AsyncMock()
    playwright_mock.chromium.launch = AsyncMock(return_value=browser_mock)

    with patch("browser.async_playwright") as mock_pw:
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=playwright_mock)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        import asyncio
        from browser import enter_lottery
        asyncio.get_event_loop().run_until_complete(
            enter_lottery({"concert_id": 6, "event_id": "11997", "artist": "The Roots", "show_date": "2026-07-12"})
        )

    page_mock.route.assert_called_once()
    route_pattern = page_mock.route.call_args[0][0]
    assert "validate-captcha" in route_pattern

    page_mock.goto.assert_called_once()
    goto_url = page_mock.goto.call_args[0][0]
    assert "11997" in goto_url
    assert "tixologi.com" in goto_url

    assert page_mock.fill.call_count >= 4
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_browser.py::test_enter_lottery_registers_captcha_route_and_navigates -v
```

Expected: `AttributeError` — `enter_lottery` not defined in `browser`.

- [ ] **Step 3: Append form functions to `browser.py`**

```python
import os


async def _handle_captcha(route) -> None:
    await route.fulfill(
        status=200,
        content_type="application/json",
        body='{"success":true,"challenge_ts":"2026-06-24T10:05:00Z","hostname":"events.tixologi.com"}',
    )


async def enter_lottery(concert: dict) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.route("**/validate-captcha**", _handle_captcha)

        url = f"https://events.tixologi.com/event/{concert['event_id']}/lottery"
        await page.goto(url, wait_until="networkidle", timeout=30000)

        # Fill form fields — selectors use comma-separated fallbacks.
        # If any selector fails on the live form, run with headless=False and
        # page.pause() to inspect the DOM and tighten selectors.
        await page.fill("input[name='firstName'], input[placeholder*='First']", os.environ["FIRST_NAME"])
        await page.fill("input[name='lastName'], input[placeholder*='Last']", os.environ["LAST_NAME"])
        await page.fill("input[name='email'], input[type='email']", os.environ["EMAIL"])
        await page.select_option("select[name='tickets'], select[name='ticketCount']", "4")
        await page.fill("input[name='zip'], input[name='zipCode']", os.environ["ZIP_CODE"])
        await page.select_option("select[name='gender']", os.environ["GENDER"])
        await page.select_option("select[name='age'], select[name='ageRange']", os.environ["AGE"])
        await page.select_option("select[name='ethnicity']", os.environ["ETHNICITY"])
        await page.select_option("select[name='income'], select[name='householdIncome']", os.environ["ANNUAL_HOUSEHOLD_INCOME"])
        await page.select_option("select[name='groups'], select[name='followingGroups']", "N/A")
        await page.check("input[type='checkbox'][name*='conduct'], input[type='checkbox'][name*='terms']")

        await page.click("button[type='submit'], input[type='submit']")

        await page.wait_for_selector(
            ".confirmation, h1:has-text('Thank'), h2:has-text('Thank'), [class*='success']",
            timeout=15000,
        )

        await browser.close()
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add browser.py tests/test_browser.py
git commit -m "feat: form filling and reCAPTCHA bypass via page.route interception"
```

---

### Task 7: Main orchestrator (`lottery.py`)

**Files:**
- Create: `lottery.py`
- Create: `tests/test_lottery.py`

**Interfaces:**
- Consumes: `load_entries`, `save_entry`, `push_state` from `state`; `find_open_lottery`, `enter_lottery` from `browser`; `send_success`, `send_failure` from `notify`
- Produces: `async main() -> None`; executable via `python lottery.py`

- [ ] **Step 1: Write failing tests — create `tests/test_lottery.py`**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

CONCERT = {
    "concert_id": 6,
    "event_id": "11997",
    "artist": "The Roots",
    "show_date": "2026-07-12",
}


async def test_main_exits_cleanly_when_no_open_lottery():
    with patch("browser.find_open_lottery", new=AsyncMock(return_value=None)), \
         patch("state.load_entries", return_value=[]), \
         patch("notify.send_success") as mock_success:
        from lottery import main
        await main()
    mock_success.assert_not_called()


async def test_main_saves_and_notifies_on_success():
    with patch("browser.find_open_lottery", new=AsyncMock(return_value=CONCERT)), \
         patch("browser.enter_lottery", new=AsyncMock()), \
         patch("state.load_entries", return_value=[]), \
         patch("state.save_entry") as mock_save, \
         patch("state.push_state") as mock_push, \
         patch("notify.send_success") as mock_success:
        from lottery import main
        await main()

    mock_save.assert_called_once()
    saved = mock_save.call_args[0][0]
    assert saved["concert_id"] == 6
    assert saved["status"] == "submitted"
    assert "entered_at" in saved

    mock_push.assert_called_once_with("The Roots", "2026-07-12")
    mock_success.assert_called_once()


async def test_main_sends_failure_email_and_does_not_save_on_exception():
    with patch("browser.find_open_lottery", new=AsyncMock(return_value=CONCERT)), \
         patch("browser.enter_lottery", new=AsyncMock(side_effect=Exception("timeout"))), \
         patch("state.load_entries", return_value=[]), \
         patch("state.save_entry") as mock_save, \
         patch("notify.send_failure") as mock_failure, \
         patch("notify.send_success") as mock_success:
        from lottery import main
        await main()

    mock_failure.assert_called_once()
    error_text = mock_failure.call_args[0][1]
    assert "timeout" in error_text
    mock_success.assert_not_called()
    mock_save.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_lottery.py -v
```

Expected: `ModuleNotFoundError: No module named 'lottery'`

- [ ] **Step 3: Implement `lottery.py`**

```python
import asyncio
import traceback
from datetime import datetime, timezone

from dotenv import load_dotenv

import browser
import notify
import state

load_dotenv()


async def main() -> None:
    entries = state.load_entries()
    concert = await browser.find_open_lottery(entries)

    if concert is None:
        print("[lottery] No open lottery found today. Exiting.")
        return

    print(f"[lottery] Open lottery found: {concert['artist']} ({concert['show_date']})")

    try:
        await browser.enter_lottery(concert)
    except Exception as exc:
        error_text = traceback.format_exc()
        print(f"[lottery] Entry failed: {exc}")
        notify.send_failure(concert, error_text)
        return

    entered_at = datetime.now(timezone.utc).isoformat()
    entry = {**concert, "entered_at": entered_at, "status": "submitted"}

    state.save_entry(entry)
    state.push_state(concert["artist"], concert["show_date"])
    notify.send_success({**concert, "entered_at": entered_at})

    print(f"[lottery] Entry submitted and state committed.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add lottery.py tests/test_lottery.py
git commit -m "feat: main orchestrator — discovery, entry, state, and notifications"
```

---

### Task 8: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/lottery.yml`

**Interfaces:**
- Consumes: GitHub Actions secrets listed in Global Constraints
- Produces: automated daily run at 10:05am PT + `workflow_dispatch` for manual testing

No unit tests — validate by triggering `workflow_dispatch` after pushing.

- [ ] **Step 1: Create `.github/workflows/lottery.yml`**

```yaml
name: Stern Grove Lottery

on:
  schedule:
    - cron: "5 17 * * *"  # 10:05am PDT (UTC-7 summer)
  workflow_dispatch:        # manual trigger for testing

jobs:
  enter-lottery:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GIT_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Install Playwright browsers
        run: playwright install chromium --with-deps

      - name: Run lottery script
        run: python lottery.py
        env:
          FIRST_NAME: ${{ secrets.FIRST_NAME }}
          LAST_NAME: ${{ secrets.LAST_NAME }}
          EMAIL: ${{ secrets.EMAIL }}
          ZIP_CODE: ${{ secrets.ZIP_CODE }}
          GENDER: ${{ secrets.GENDER }}
          AGE: ${{ secrets.AGE }}
          ETHNICITY: ${{ secrets.ETHNICITY }}
          ANNUAL_HOUSEHOLD_INCOME: ${{ secrets.ANNUAL_HOUSEHOLD_INCOME }}
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          RESEND_FROM: ${{ secrets.RESEND_FROM }}
          NOTIFY_EMAIL: ${{ secrets.NOTIFY_EMAIL }}
          GIT_TOKEN: ${{ secrets.GIT_TOKEN }}
          GIT_REPO: ${{ secrets.GIT_REPO }}
```

- [ ] **Step 2: Verify all GitHub Actions secrets exist**

In the repo on GitHub → Settings → Secrets and variables → Actions, confirm every secret is set:

`FIRST_NAME`, `LAST_NAME`, `EMAIL`, `ZIP_CODE`, `GENDER`, `AGE`, `ETHNICITY`, `ANNUAL_HOUSEHOLD_INCOME`, `RESEND_API_KEY`, `RESEND_FROM`, `NOTIFY_EMAIL`, `GIT_TOKEN`, `GIT_REPO`

`GIT_REPO` format: `owner/repo-name` (e.g. `elizabethsiegle/stern-grove-lottery`)
`NOTIFY_EMAIL`: the address that receives success/failure emails (e.g. `lizzie@entire.io`)

- [ ] **Step 3: Push and trigger a manual run**

```bash
git add .github/workflows/lottery.yml
git commit -m "ci: daily GitHub Actions cron for Stern Grove lottery"
git push
```

Then: GitHub repo → Actions tab → "Stern Grove Lottery" → "Run workflow" → Run.

Verify:
- Run completes without error
- If a lottery is open: success email arrives at `NOTIFY_EMAIL` and `entered-lotteries.json` has a new commit
- If no lottery is open: run exits with log `No open lottery found today`
