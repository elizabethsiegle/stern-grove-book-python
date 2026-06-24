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
