import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5433/petcare",
)
CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "24"))
