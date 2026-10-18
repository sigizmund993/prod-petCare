import logging
from pathlib import Path

import psycopg

log = logging.getLogger("uvicorn.error")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "sql"
# Произвольный ключ advisory-блокировки: два экземпляра приложения не применят миграции одновременно
LOCK_KEY = 8_020_419


def migrate(dsn: str) -> None:
    # Применяет sql/*.sql по порядку имён; применённые записываются в schema_migrations.
    # Каждый файл — в своей транзакции: при ошибке он откатывается, а приложение не стартует
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            applied = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name in applied:
                    continue
                log.info("Применяю миграцию %s", path.name)
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
