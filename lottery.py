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
    notify.send_success(entry)

    print("[lottery] Entry submitted and state committed.")


if __name__ == "__main__":
    asyncio.run(main())
