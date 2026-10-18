import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5433/petcare",
)
CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "24"))

# Подтверждение почты
EMAIL_CODE_TTL_MINUTES = int(os.getenv("EMAIL_CODE_TTL_MINUTES", "15"))
EMAIL_CODE_MAX_ATTEMPTS = int(os.getenv("EMAIL_CODE_MAX_ATTEMPTS", "5"))
EMAIL_CODE_RESEND_SECONDS = int(os.getenv("EMAIL_CODE_RESEND_SECONDS", "60"))

# SMTP. Без SMTP_HOST письма пишутся в лог
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USER
SMTP_TLS = os.getenv("SMTP_TLS", "starttls")  # starttls | ssl | none

# Telegram. Без TELEGRAM_BOT_TOKEN бот не запускается и уведомления не шлются
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")  # без @
TELEGRAM_LINK_TTL_MINUTES = int(os.getenv("TELEGRAM_LINK_TTL_MINUTES", "15"))
# Часовой пояс, в котором показываем даты в уведомлениях
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
