import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5433/petcare",
)
# CORS: список origin через запятую. Плюс, если CORS_ALLOW_LOCALHOST включён,
# любой http(s)://localhost:<порт> и 127.0.0.1:<порт>, чтобы фронт можно было запускать локально
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGIN", "").split(",") if o.strip()]
CORS_ALLOW_LOCALHOST = os.getenv("CORS_ALLOW_LOCALHOST", "1").lower() in ("1", "true", "yes")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "24"))
# Часовой пояс, в котором наступает «сегодня» для дней рождения питомцев
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

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
