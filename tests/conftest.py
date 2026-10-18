import os
import re

import psycopg
import pytest

# Тесты пересоздают схему БД, поэтому базу нужно указать явно, чтобы не снести рабочую
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.exit("Задайте TEST_DATABASE_URL — отдельную БД для тестов (её схема будет пересоздана)", returncode=2)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256")

from fastapi.testclient import TestClient

from db.migrate import migrate
from src import handlers_user
from src.main import app

TABLES = "birthday_reads, notification_reads, email_codes, props, pets, users"


def _sql(query: str) -> None:
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(query)


@pytest.fixture(scope="session", autouse=True)
def schema():
    # Применяем миграции тем же migrate(), что и приложение при старте
    _sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    migrate(TEST_DATABASE_URL)


@pytest.fixture(autouse=True)
def clean_db():
    _sql(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sql():
    # Прямой доступ к БД, чтобы подготовить состояние, которого не добиться через API (например, «прошли сутки»)
    def run(query: str, params=None):
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
            cur = conn.execute(query, params)
            return cur.fetchall() if cur.description else None

    return run


@pytest.fixture
def mailbox(monkeypatch):
    # Вместо SMTP складываем письма в список
    sent = []
    monkeypatch.setattr(handlers_user, "send_mail", lambda to, subject, body: sent.append({"to": to, "body": body}))
    return sent


def code_from(mail: dict) -> str:
    return re.search(r"\b(\d{6})\b", mail["body"]).group(1)


@pytest.fixture
def register(client, mailbox):
    # Регистрирует и подтверждает пользователя; возвращает (user, headers)
    def make(email: str = "owner@example.com", passwd: str = "secret", name: str = "Иван"):
        user = client.post("/user/add", json={"email": email, "passwd": passwd, "name": name}).json()
        mail = next(m for m in reversed(mailbox) if m["to"] == email)
        token = client.post("/user/verify", json={"email": email, "code": code_from(mail)}).json()["access_token"]
        return user, {"Authorization": f"Bearer {token}"}

    return make
