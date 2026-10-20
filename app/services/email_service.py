import os
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


def send_email(
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """Send a plain-text email using the configured SMTP server."""
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL")
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"

    if not all([host, username, password, from_email]):
        raise RuntimeError(
            "SMTP configuration is incomplete. Check the SMTP variables in .env."
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = recipient
    message.set_content(body)

    context = ssl.create_default_context()

    if use_tls:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP_SSL(
            host,
            port,
            timeout=20,
            context=context,
        ) as server:
            server.login(username, password)
            server.send_message(message)
