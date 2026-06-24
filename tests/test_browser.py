import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch


OPEN_TS = "2026-06-14T10:00:00-07:00"
CLOSE_TS = "2026-06-21T10:00:00-07:00"
PAST_CLOSE_TS = "2026-06-10T10:00:00-07:00"

CONCERT_RAW = {
    "eventId": 11997,
    "open": OPEN_TS,
    "close": CLOSE_TS,
    "dateMatch": "june 14",
}
INDEX = 6


def test_is_lottery_open_within_window():
    from browser import _is_lottery_open
    now = datetime(2026, 6, 17, 17, 5, tzinfo=timezone.utc)  # within the window (UTC equiv of PDT range)
    assert _is_lottery_open(CONCERT_RAW, now) is True


def test_is_lottery_open_before_window():
    from browser import _is_lottery_open
    now = datetime(2026, 6, 14, 16, 59, tzinfo=timezone.utc)  # just before open (10:00 PDT = 17:00 UTC)
    assert _is_lottery_open(CONCERT_RAW, now) is False


def test_is_lottery_open_after_window():
    from browser import _is_lottery_open
    closed = dict(CONCERT_RAW, close=PAST_CLOSE_TS)
    now = datetime(2026, 6, 17, 17, 5, tzinfo=timezone.utc)
    assert _is_lottery_open(closed, now) is False


def test_is_already_entered_true():
    from browser import _is_already_entered
    entries = [{"concert_id": INDEX}]
    assert _is_already_entered(INDEX, entries) is True


def test_is_already_entered_false():
    from browser import _is_already_entered
    entries = [{"concert_id": 5}]
    assert _is_already_entered(INDEX, entries) is False


def test_concert_to_entry_shape():
    from browser import _concert_to_entry_shape
    result = _concert_to_entry_shape(INDEX, CONCERT_RAW, "The Roots")
    assert result == {
        "concert_id": INDEX,
        "event_id": "11997",
        "artist": "The Roots",
        "show_date": "june 14",
    }


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
            enter_lottery({"concert_id": 6, "event_id": "11997", "artist": "The Roots", "show_date": "june 14"})
        )

    page_mock.route.assert_called_once()
    route_pattern = page_mock.route.call_args[0][0]
    assert "validate-captcha" in route_pattern

    page_mock.goto.assert_called_once()
    goto_url = page_mock.goto.call_args[0][0]
    assert "11997" in goto_url
    assert "tixologi.com" in goto_url

    assert page_mock.fill.call_count >= 4
