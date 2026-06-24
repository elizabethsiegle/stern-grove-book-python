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
