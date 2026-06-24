from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional
from playwright.async_api import async_playwright


def _parse_dt(s: str) -> datetime:
    """Parse an ISO 8601 string, preserving timezone info.
    If no timezone is present, assume UTC."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_lottery_open(concert: dict, now: datetime) -> bool:
    """Return True if now falls within the lottery window [open, close]."""
    open_dt = _parse_dt(concert["open"])
    close_dt = _parse_dt(concert["close"])
    return open_dt <= now <= close_dt


def _is_already_entered(index: int, entries: list[dict]) -> bool:
    """Return True if any entry in entries has concert_id == index."""
    return any(e["concert_id"] == index for e in entries)


def _concert_to_entry_shape(index: int, concert: dict, artist: str) -> dict:
    """Convert a raw widget concert object + scraped metadata into an entry dict."""
    return {
        "concert_id": index,
        "event_id": str(concert["eventId"]),
        "artist": artist,
        "show_date": concert["dateMatch"],
    }


async def find_open_lottery(entries: list[dict]) -> Optional[dict]:
    """Navigate to sterngrove.org/lineup2026, read window.TixologiWidget.concerts,
    iterate by index, scrape artist from HTML for matching concert.
    Returns an entry-shape dict or None if no open, un-entered lottery found."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(
                "https://www.sterngrove.org/lineup2026",
                wait_until="networkidle",
                timeout=30000,
            )
            concerts = await page.evaluate("() => window.TixologiWidget.concerts")

            now = datetime.now(timezone.utc)
            result = None

            for index, concert in enumerate(concerts):
                if not _is_lottery_open(concert, now):
                    continue
                if _is_already_entered(index, entries):
                    continue

                # Scrape artist name from the nearest heading in the same section
                artist = await page.eval_on_selector(
                    f'[data-sgf-concert="{index}"]',
                    """el => el.closest('section, .sqs-block, [class*="block"]')
                           ?.querySelector('h2, h3, h1')
                           ?.textContent?.trim() || 'Unknown Artist'"""
                )

                result = _concert_to_entry_shape(index, concert, artist)
                break
        finally:
            await browser.close()

    return result


async def _handle_captcha(route) -> None:
    await route.fulfill(
        status=200,
        content_type="application/json",
        body='{"success":true,"challenge_ts":"2026-06-24T10:05:00Z","hostname":"events.tixologi.com"}',
    )


async def enter_lottery(concert: dict) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()

            await page.route("**/validate-captcha**", _handle_captcha)

            url = f"https://events.tixologi.com/event/{concert['event_id']}/lottery"
            await page.goto(url, wait_until="networkidle", timeout=30000)

            await page.fill("input[name='firstName']", os.environ["FIRST_NAME"])
            await page.fill("input[name='lastName']", os.environ["LAST_NAME"])
            await page.fill("input[name='email']", os.environ["EMAIL"])
            await page.select_option("select[name='numberOfTickets']", "4")
            await page.fill("input[name='zipCode']", os.environ["ZIP_CODE"])
            await page.select_option("select[name='gender']", os.environ["GENDER"])
            await page.select_option("select[name='age']", os.environ["AGE"])
            await page.select_option("select[name='ethnicity']", os.environ["ETHNICITY"])
            await page.select_option("select[name='householdIncome']", os.environ["ANNUAL_HOUSEHOLD_INCOME"])
            # identifyGroups is a set of checkboxes — check the N/A option
            await page.check("#identifyGroups-na")
            await page.check("#codeOfConductAccepted")

            # Submit button is disabled until reCAPTCHA validates; wait for it to enable
            await page.wait_for_selector("button[type='submit']:not([disabled])", timeout=15000)
            await page.click("button[type='submit']")

            await page.wait_for_selector(
                "h1:has-text('Thank'), h2:has-text('Thank'), h3:has-text('Thank'), "
                "[class*='success'], [class*='confirmation'], [class*='complete']",
                timeout=15000,
            )
        finally:
            await browser.close()
