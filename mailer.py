import logging
import os
import httpx

log = logging.getLogger("elephant.mailer")
RESEND_URL = "https://api.resend.com/emails"

def send_admin_alert(subject: str, body: str) -> dict:
    key = os.getenv("RESEND_API_KEY", "")
    to = os.getenv("ADMIN_ALERT_EMAIL", "")
    sender = os.getenv("RESEND_FROM", "")
    if not (key and to and sender):
        raise RuntimeError("Admin alert not sent: RESEND_API_KEY, ADMIN_ALERT_EMAIL and RESEND_FROM are required")
    response = httpx.post(RESEND_URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          json={"from": sender, "to": [to], "subject": subject, "text": body}, timeout=12)
    response.raise_for_status()
    return {"sent": True, "id": response.json().get("id")}
