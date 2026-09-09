from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_digest(html: Path, markdown: Path, subject: str) -> None:
    required = [
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "EMAIL_FROM",
        "EMAIL_TO",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing SMTP environment variables: {', '.join(missing)}")
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = (
        subject,
        os.environ["EMAIL_FROM"],
        os.environ["EMAIL_TO"],
    )
    message.set_content("Your email client does not support HTML. See attached digest.")
    message.add_alternative(html.read_text(encoding="utf-8"), subtype="html")
    for path, mime in ((markdown, "text/markdown"), (html, "text/html")):
        main, sub = mime.split("/")
        message.add_attachment(path.read_bytes(), maintype=main, subtype=sub, filename=path.name)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as server:
        server.starttls()
        server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        server.send_message(message)
