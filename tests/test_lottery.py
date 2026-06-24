import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_main_exits_cleanly_when_no_open_lottery():
    with patch("browser.find_open_lottery", new=AsyncMock(return_value=None)), \
         patch("state.load_entries", return_value=[]), \
         patch("notify.send_success") as mock_success, \
         patch("notify.send_failure") as mock_failure:
        from lottery import main
        await main()
    mock_success.assert_not_called()
    mock_failure.assert_not_called()


@pytest.mark.asyncio
async def test_main_saves_and_notifies_on_success():
    CONCERT = {"concert_id": 6, "event_id": "11997", "artist": "The Roots", "show_date": "june 14"}
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
    mock_push.assert_called_once_with("The Roots", "june 14")
    mock_success.assert_called_once()


@pytest.mark.asyncio
async def test_main_sends_failure_email_and_does_not_save_on_exception():
    CONCERT = {"concert_id": 6, "event_id": "11997", "artist": "The Roots", "show_date": "june 14"}
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
