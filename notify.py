import logging
import os
import resend

logger = logging.getLogger(__name__)


def _init_resend() -> None:
    """Initialize Resend API key from environment."""
    resend.api_key = os.environ["RESEND_API_KEY"]


def send_success(concert: dict) -> None:
    _init_resend()
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
        logger.exception("Resend error (success email): %s", exc)


def send_failure(concert: dict, error_text: str) -> None:
    _init_resend()
    try:
        resend.Emails.send({
            "from": os.environ["RESEND_FROM"],
            "to": [os.environ["NOTIFY_EMAIL"]],
            "subject": f"Stern Grove lottery FAILED — {concert['artist']} ({concert['show_date']})",
            "text": f"Error:\n\n{error_text}",
        })
    except Exception as exc:
        logger.exception("Resend error (failure email): %s", exc)
