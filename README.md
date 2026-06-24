# Stern Grove Lottery Bot

A headless automation that watches for open Stern Grove Festival ticket lotteries, fills the registration form, and emails you the result — daily, hands-free, via GitHub Actions.

## How it works

1. **Discover open lotteries** — A headless Chromium browser loads `sterngrove.org/lineup2026` and reads `window.TixologiWidget.concerts` — a JavaScript object Stern Grove injects at page load containing each concert's lottery open and close datetimes. The script compares the current time against those windows and skips any concert already recorded in `entered-lotteries.json`.

2. **Navigate to the registration form** — Once an eligible concert is found, the browser navigates to the Tixologi registration form at `events.tixologi.com/event/{id}/lottery`. Before loading the page, a `page.route()` intercept is registered so that any `validate-captcha` network request is fulfilled with a synthetic success response — the real registration POST still goes through normally.

3. **Fill and submit the form** — All personal and demographic fields are filled from environment variables: first name, last name, email, 4 tickets, zip code, gender, age range, ethnicity, annual household income, N/A for group affiliation, and the code of conduct checkbox. The script waits for the submit button to become enabled (it starts disabled pending CAPTCHA validation), then clicks it and waits for a confirmation element.

4. **Send a notification email** — On success, a confirmation email is sent via [Resend](https://resend.com) with the artist, show date, and entry timestamp. On any failure, an error email is sent with the full traceback.

5. **Record the entry and commit** — The successful entry is appended to `entered-lotteries.json` and committed back to the repository using a GitHub PAT — so the next run's duplicate-entry check sees the full history even across fresh runner environments.

## Stack

| Tool | Role |
|---|---|
| [Playwright](https://playwright.dev) | Headless browser automation |
| [Resend](https://resend.com) | Transactional email |
| [GitHub Actions](https://github.com/features/actions) | Daily cron (`5 17 * * *` — 10:05am PDT) |
| [Entire](https://entire.io) | Agentic git |

Stern Grove lotteries open 6 weeks before each show at 10am and stay open for one week. The script enters at most one lottery per run.

## GitHub Actions setup

Fork or clone the repo, then add the following secrets under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `FIRST_NAME` | Your first name |
| `LAST_NAME` | Your last name |
| `EMAIL` | Email for the lottery registration |
| `ZIP_CODE` | Your zip code |
| `GENDER` | `male`, `female`, `non-binary`, `other`, or `prefer-not-to-answer` |
| `AGE` | `under-18`, `18-24`, `25-34`, `35-44`, `45-54`, `55-64`, or `65-plus` |
| `ETHNICITY` | `asian`, `black`, `hispanic`, `middle-eastern`, `native-american`, `white`, `mixed`, `other`, or `prefer-not-to-answer` |
| `ANNUAL_HOUSEHOLD_INCOME` | `under-40k`, `40k-80k`, `80k-120k`, `120k-200k`, `200k-500k`, `500k-plus`, or `prefer-not-to-answer` |
| `RESEND_API_KEY` | API key from resend.com |
| `RESEND_FROM` | Verified sender address, e.g. `bot@yourdomain.com` |
| `NOTIFY_EMAIL` | Where to send success/failure notifications |
| `GIT_TOKEN` | GitHub PAT with `repo` scope, for committing state |
| `GIT_REPO` | Format: `owner/repo-name` |

Trigger a manual test run from **Actions → Stern Grove Lottery → Run workflow**.

## Running locally

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium --with-deps

# Copy and fill in your env vars
cp .env.example .env

# Run
python3 lottery.py
```

If a lottery is open today, the script enters it and commits the result. If nothing is open it exits cleanly with a log message.

```bash
# Run tests
pytest tests/ -v
# 21 passed
```

## State file

`entered-lotteries.json` is committed to the repo after every successful entry:

```json
[
  {
    "concert_id": 7,
    "event_id": "11998",
    "artist": "Khruangbin",
    "show_date": "june 28",
    "entered_at": "2026-06-21T17:07:44+00:00",
    "status": "submitted"
  }
]
```

The `concert_id` is the zero-based index into `window.TixologiWidget.concerts`, which the script checks before entering to prevent duplicate submissions.
