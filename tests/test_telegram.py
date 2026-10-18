from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from src import config, telegram


def at(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat()


@pytest.fixture
def bot(monkeypatch):
    # Вместо Telegram API складываем сообщения в список
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(config, "TELEGRAM_BOT_USERNAME", "petcare_test_bot")
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda chat_id, text: sent.append((chat_id, text)) or True)
    return sent


def start(chat_id: int, text: str) -> None:
    telegram.handle_update({"update_id": 1, "message": {"chat": {"id": chat_id, "type": "private"}, "text": text}})


@pytest.fixture
def linked(client, register, bot, sql):
    # Пользователь с привязанным Telegram; привязка «давно», чтобы записи из прошлого считались новыми
    def make(email: str = "owner@example.com", chat_id: int = 1001):
        user, headers = register(email)
        url = client.post("/user/telegram/link", headers=headers).json()["url"]
        start(chat_id, f"/start {url.split('start=')[1]}")
        sql("UPDATE users SET telegram_linked_at = now() - interval '2 days' WHERE id = %s", (user["id"],))
        bot.clear()
        return user, headers

    return make


def test_link_flow(client, register, bot):
    _, headers = register()
    r = client.post("/user/telegram/link", headers=headers)
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("https://t.me/petcare_test_bot?start=")

    start(555, f"/start {url.split('start=')[1]}")
    assert client.get("/user/me", headers=headers).json()["telegram_linked"] is True
    assert "Готово" in bot[-1][1]

    # Код одноразовый
    start(777, f"/start {url.split('start=')[1]}")
    assert "недействительна" in bot[-1][1]


def test_link_without_bot_configured(client, register):
    _, headers = register()
    assert client.post("/user/telegram/link", headers=headers).status_code == 503


def test_unlink(client, linked):
    _, headers = linked()
    assert client.delete("/user/telegram", headers=headers).status_code == 204
    assert client.get("/user/me", headers=headers).json()["telegram_linked"] is False


def test_stop_command_unlinks(client, linked):
    _, headers = linked(chat_id=42)
    start(42, "/stop")
    assert client.get("/user/me", headers=headers).json()["telegram_linked"] is False


def test_due_prop_sent_once(client, linked, bot):
    _, headers = linked()
    client.post("/prop/add", json={"name": "Прививка", "msg": "Не забыть паспорт", "date": at(-timedelta(hours=1))}, headers=headers)
    client.post("/prop/add", json={"name": "Позже", "date": at(timedelta(hours=1))}, headers=headers)

    telegram.send_due()
    assert len(bot) == 1
    chat_id, text = bot[0]
    assert chat_id == 1001 and "Прививка" in text and "Не забыть паспорт" in text

    telegram.send_due()
    assert len(bot) == 1


def test_sent_to_every_linked_owner(client, linked, register, bot):
    _, alice_h = linked("alice@example.com", chat_id=1)
    bob, _ = linked("bob@example.com", chat_id=2)
    carol, _ = register("carol@example.com")
    client.post("/prop/add", json={"name": "Прививка", "date": at(-timedelta(hours=1)), "own_ids": [bob["id"], carol["id"]]}, headers=alice_h)

    telegram.send_due()
    assert sorted(chat_id for chat_id, _ in bot) == [1, 2]


def test_history_before_linking_not_sent(client, register, bot):
    _, headers = register()
    client.post("/prop/add", json={"name": "Давно", "date": at(-timedelta(days=30))}, headers=headers)
    url = client.post("/user/telegram/link", headers=headers).json()["url"]
    start(1001, f"/start {url.split('start=')[1]}")
    bot.clear()

    telegram.send_due()
    assert bot == []


def test_read_on_site_not_sent(client, linked, bot):
    _, headers = linked()
    prop = client.post("/prop/add", json={"name": "Прививка", "date": at(-timedelta(hours=1))}, headers=headers).json()
    client.post("/notification/read", params={"prop_id": prop["id"]}, headers=headers)

    telegram.send_due()
    assert bot == []


def test_food_not_sent(client, linked, bot):
    _, headers = linked()
    client.post("/prop/add", json={"name": "Корм", "category": "food", "date": at(-timedelta(hours=1))}, headers=headers)

    telegram.send_due()
    assert bot == []


def test_repeating_prop_sent_again_next_day(client, linked, bot, sql):
    _, headers = linked()
    client.post("/prop/add", json={"name": "Таблетка", "rep": True, "date": at(-timedelta(days=1, hours=1))}, headers=headers)

    telegram.send_due()
    assert len(bot) == 1
    # «Прошли сутки»: прошлое срабатывание отправлено, текущее — ещё нет
    sql("UPDATE telegram_sent SET sent_date = sent_date - interval '1 day'")
    telegram.send_due()
    assert len(bot) == 2


def test_birthday_sent_once(client, linked, bot, monkeypatch):
    monkeypatch.setattr(telegram, "BIRTHDAY_HOUR", 0)
    _, headers = linked()
    today = datetime.now(ZoneInfo(config.TIMEZONE)).date()
    # 29 февраля в невисокосный год сдвигает день рождения, такой день для теста не годится
    if (today.month, today.day) == (2, 29):
        pytest.skip("29 февраля")
    birth = today.replace(year=today.year - 3)
    client.post("/pet/add", json={"name": "Барсик", "birth_date": birth.isoformat()}, headers=headers)

    telegram.send_due()
    assert len(bot) == 1 and "Барсик" in bot[0][1] and "Исполняется 3 года" in bot[0][1]
    telegram.send_due()
    assert len(bot) == 1


def test_birthday_waits_for_morning(client, linked, bot, monkeypatch):
    monkeypatch.setattr(telegram, "BIRTHDAY_HOUR", 24)
    _, headers = linked()
    today = datetime.now(ZoneInfo(config.TIMEZONE)).date()
    if (today.month, today.day) == (2, 29):
        pytest.skip("29 февраля")
    client.post("/pet/add", json={"name": "Барсик", "birth_date": today.replace(year=today.year - 3).isoformat()}, headers=headers)

    telegram.send_due()
    assert bot == []


def test_blocked_bot_unlinks(client, linked, monkeypatch):
    _, headers = linked(chat_id=99)
    monkeypatch.undo()  # настоящий send_message, но без сети
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(403))

    telegram.send_message(99, "привет")
    assert client.get("/user/me", headers=headers).json()["telegram_linked"] is False


def test_failed_send_retried_next_round(client, linked, monkeypatch):
    _, headers = linked()
    client.post("/prop/add", json={"name": "Прививка", "date": at(-timedelta(hours=1))}, headers=headers)
    attempts = []
    monkeypatch.setattr(telegram, "send_message", lambda chat_id, text: attempts.append(text) or len(attempts) > 1)

    telegram.send_due()  # Telegram недоступен — отметки нет
    telegram.send_due()  # повтор успешен
    telegram.send_due()  # больше не шлём
    assert len(attempts) == 2


@pytest.mark.parametrize(("status", "delivered"), [(200, True), (400, True), (429, False), (502, False)])
def test_send_message_reports_temporary_failures(monkeypatch, status, delivered):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(status))
    assert telegram.send_message(99, "привет") is delivered


def test_send_message_network_error_is_temporary(monkeypatch):
    def fail(*a, **kw):
        raise httpx.ConnectError("нет сети")

    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(httpx, "post", fail)
    assert telegram.send_message(99, "привет") is False
