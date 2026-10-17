import logging
import smtplib
from email.message import EmailMessage

from src import config

log = logging.getLogger("uvicorn.error")


def send_mail(to: str, subject: str, body: str) -> None:
    # Без SMTP_HOST письмо не отправляется, а пишется в лог (для локальной разработки)
    if not config.SMTP_HOST:
        log.warning("SMTP_HOST не задан, письмо для %s: %s\n%s", to, subject, body)
        return

    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if config.SMTP_TLS == "ssl":
            smtp = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=10)
        else:
            smtp = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10)
        with smtp:
            if config.SMTP_TLS == "starttls":
                smtp.starttls()
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        log.exception("Не удалось отправить письмо на %s", to)
