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
