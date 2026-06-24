# Stern Grove Lottery Automation — Design Spec

**Date:** 2026-06-24
**Status:** Approved

---

## Overview

A Python + Playwright script, triggered daily by GitHub Actions, that detects open Stern Grove Festival lottery windows and automatically submits an entry. State is tracked in a JSON file committed back to the repo after each entry, preventing double-entries. Success and failure outcomes are reported by email via Resend.

---

## Architecture

```
GitHub Actions cron (daily, 10:05am PT / 17:05 UTC)
    └── lottery.py
          ├── 1. Load entered-lotteries.json
          ├── 2. Playwright: navigate to sterngrove.org/lineup2026
          ├── 3. page.evaluate() → read window.TixologiWidget.concerts
          ├── 4. Find concert with open lottery not already entered
          ├── 5. Navigate to events.tixologi.com/event/{id}/lottery
          ├── 6. page.route() → intercept validate-captcha → return fake success
          ├── 7. Fill and submit form
          ├── 8. Send Resend email (success or failure)
          └── 9. Append entry to entered-lotteries.json, commit to repo
```

---

## Concert Discovery

- Navigate to `https://www.sterngrove.org/lineup2026` using headless Chromium
- Wait for the page to fully load so the Tixologi widget script executes
- Call `page.evaluate("() => window.TixologiWidget.concerts")` to get the full concert list as a Python dict
- Each concert object's exact schema must be inspected at implementation time (log `window.TixologiWidget.concerts` in a one-off run). Expected fields: `id` (matches `data-sgf-concert`), `tixologi_event_id` (matches `data-tixologi-event-id`), and date/status fields indicating whether the lottery window is open
- Filter to concerts where:
  - The current datetime is within the lottery window (`lottery_open <= now <= lottery_close`)
  - The concert's `id` is not already in `entered-lotteries.json`
- If multiple open lotteries exist, enter only the first (one per week rule)
- If none match, log and exit with code 0 — no email sent

---

## State Management

**File:** `entered-lotteries.json` in the repo root

**Schema:**
```json
[
  {
    "concert_id": 6,
    "event_id": "11997",
    "artist": "Artist Name",
    "show_date": "2026-07-12",
    "entered_at": "2026-06-14T10:07:23Z",
    "status": "submitted"
  }
]
```

- Loaded at script start; missing file treated as empty list
- Appended to on successful submission
- Committed and pushed using the `GIT_TOKEN` PAT via HTTPS (`https://x-access-token:{GIT_TOKEN}@github.com/{GIT_REPO}`)
- Git commit message: `chore: record lottery entry for {artist} {show_date}`
- On git push failure: log the error but do not re-raise — the entry still happened; the duplicate-entry guard is best-effort

---

## Form Filling

**Target URL:** `https://events.tixologi.com/event/{event_id}/lottery`

**reCAPTCHA bypass:**
```python
async def handle_captcha(route):
    await route.fulfill(
        status=200,
        content_type="application/json",
        body='{"success":true,"challenge_ts":"2026-06-24T10:05:00Z","hostname":"events.tixologi.com"}'
    )

await page.route("**/validate-captcha**", handle_captcha)
```

Only the CAPTCHA validation call is intercepted. The actual registration POST fires normally.

**Fill order (matches UI flow):**
1. First name text input
2. Last name text input
3. Email text input
4. Ticket count → select `4`
5. ZIP code text input
6. Gender dropdown
7. Age range dropdown
8. Ethnicity dropdown
9. Annual household income dropdown
10. "Following groups" → select `N/A`
11. Code of conduct checkbox → check

**Wait strategy:** After submit, wait for a success confirmation element (e.g., `.confirmation`, `h1:has-text("Thank")`, or network idle) with a 15-second timeout. If the element does not appear, raise an exception to trigger the failure email.

**All field values** come from environment variables (`FIRST_NAME`, `LAST_NAME`, `EMAIL`, `ZIP_CODE`, `GENDER`, `AGE`, `ETHNICITY`, `ANNUAL_HOUSEHOLD_INCOME`).

---

## Notifications

Sent via the [Resend Python SDK](https://resend.com/docs/send-with-python).

**Success email:**
- **To:** `NOTIFY_EMAIL`
- **From:** `RESEND_FROM`
- **Subject:** `Stern Grove lottery entered — {artist} ({show_date})`
- **Body (text):** Artist, show date, tickets requested (4), timestamp

**Failure email:**
- **To:** `NOTIFY_EMAIL`
- **From:** `RESEND_FROM`
- **Subject:** `Stern Grove lottery FAILED — {artist} ({show_date})`
- **Body (text):** Error class, message, and last 10 lines of traceback

Resend errors are caught and logged but do not re-raise — a notification failure should not mask the underlying lottery result.

---

## GitHub Actions Workflow

**File:** `.github/workflows/lottery.yml`

```yaml
name: Stern Grove Lottery

on:
  schedule:
    - cron: "5 17 * * *"   # 10:05am PT (UTC-7 summer)
  workflow_dispatch:         # manual trigger for testing

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

      - run: pip install -r requirements.txt

      - run: playwright install chromium --with-deps

      - run: python lottery.py
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

---

## File Layout

```
lottery.py                        # main script
entered-lotteries.json            # state file (committed to repo)
requirements.txt                  # playwright, python-dotenv, resend
.github/workflows/lottery.yml     # cron workflow
.env                              # local dev only (gitignored)
.env.example                      # already exists
```

**`requirements.txt`:**
```
playwright==1.44.0
python-dotenv==1.0.1
resend==2.3.0
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| No open lottery today | Exit 0, no email |
| Already entered this concert | Skip it, continue |
| Page load timeout | Raise → failure email |
| CAPTCHA intercept not matched | Form submit fails → failure email |
| Form field not found | Raise → failure email |
| Success element not found | Raise → failure email |
| Resend API error | Log, do not raise |
| Git push error | Log, do not raise |

---

## Out of Scope

- Entering multiple lotteries in one run (one per week, by design)
- Browserbase fallback (Playwright preferred; Browserbase key is available but unused)
- Parsing show dates to pre-compute schedule (script detects open windows dynamically)
- Retry logic on failed form submissions (one attempt per run; next day's cron is the retry)
