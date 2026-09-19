import logging
import smtplib
from email.message import EmailMessage

from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger("app.account_email")


def send_account_email(*, recipient: str, subject: str, text: str, action_url: str) -> None:
    """Deliver an account email without exposing credentials or stored token hashes."""
    if not settings.SMTP_HOST:
        if settings.ENV.strip().lower() in {"development", "dev", "test", "testing"}:
            logger.info("account_email local recipient=%s subject=%s url=%s", recipient, subject, action_url)
            return
        raise HTTPException(status_code=503, detail="Dịch vụ email chưa được cấu hình")

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(f"{text}\n\n{action_url}")
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
            if settings.SMTP_USE_TLS:
                client.starttls()
            if settings.SMTP_USERNAME:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        logger.warning("account_email delivery failed error_type=%s", type(error).__name__)
        raise HTTPException(status_code=503, detail="Không thể gửi email lúc này") from error
