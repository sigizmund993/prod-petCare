import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from db import queries
from src import config
from src.helpers import hash_telegram_code, years_word

log = logging.getLogger("uvicorn.error")

POLL_TIMEOUT = 30  # секунд, long polling
NOTIFY_INTERVAL = 60  # секунд между проверками наступивших уведомлений
BIRTHDAY_HOUR = 9


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"


def send_message(chat_id: int, text: str) -> None:
    # В логи пишем только тип ошибки: в тексте исключений httpx есть URL с токеном бота
    try:
        r = httpx.post(_url("sendMessage"), json={"chat_id": chat_id, "text": text}, timeout=10)
    except httpx.HTTPError as e:
        log.warning("Telegram sendMessage в %s: %s", chat_id, type(e).__name__)
        return
    if r.status_code == 403:
        # Пользователь заблокировал бота: отвязываем, чтобы не слать впустую
        queries.unlink_telegram_chat(chat_id)
    elif not r.is_success:
        log.warning("Telegram sendMessage в %s: %s %s", chat_id, r.status_code, r.text)


def _prop_text(prop: dict) -> str:
    date = prop["date"].astimezone(ZoneInfo(config.TIMEZONE)).strftime("%d.%m.%Y %H:%M")
    lines = [f"🔔 {prop['name']}", f"📅 {date}"]
    lines += [line for line in (prop["msg"], prop["text"]) if line]
    return "\n".join(lines)


def _birthday_text(pet: dict) -> str:
    # Тот же текст, что в уведомлении на сайте (handlers_notification.birthday_notification)
    return f"🎂 День рождения: {pet['name']}\nИсполняется {pet['years']} {years_word(pet['years'])}"


def send_due() -> None:
    # Дублирует в Telegram уведомления, наступившие на сайте. Отметку ставим после отправки:
    # если процесс упадёт посередине, сообщение придёт ещё раз, но не потеряется
    for prop in queries.list_telegram_due_props():
        send_message(prop["telegram_chat_id"], _prop_text(prop))
        queries.mark_telegram_sent(prop["user_id"], prop["id"], prop["date"])

    # Дни рождения шлём не в полночь, а с BIRTHDAY_HOUR по местному времени
    if datetime.now(ZoneInfo(config.TIMEZONE)).hour >= BIRTHDAY_HOUR:
        for pet in queries.list_telegram_birthdays(config.TIMEZONE):
            send_message(pet["telegram_chat_id"], _birthday_text(pet))
            queries.mark_telegram_birthday_sent(pet["user_id"], pet["id"], pet["day"])


async def notify_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(send_due)
        except Exception:
            log.exception("Не удалось разослать уведомления в Telegram")
        await asyncio.sleep(NOTIFY_INTERVAL)


def handle_update(update: dict) -> None:
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":
        return
    chat_id, text = chat["id"], (msg.get("text") or "").strip()

    if text.startswith("/start"):
        code = text.removeprefix("/start").strip()
        if not code:
            send_message(chat_id, "Чтобы получать уведомления, нажмите «Подключить Telegram» в профиле на сайте PetCare.")
        elif queries.link_telegram(hash_telegram_code(code), chat_id):
            send_message(chat_id, "Готово! Уведомления PetCare будут приходить сюда. Отключить: /stop")
        else:
            send_message(chat_id, "Ссылка недействительна или устарела. Получите новую на сайте.")
    elif text == "/stop":
        queries.unlink_telegram_chat(chat_id)
        send_message(chat_id, "Уведомления отключены. Подключить снова можно в профиле на сайте.")


async def run() -> None:
    await asyncio.gather(poll_updates(), notify_loop())


async def poll_updates() -> None:
    # Long polling вместо вебхука: не нужен публичный HTTPS. Опрашивать бота может только один процесс
    offset = 0
    async with httpx.AsyncClient(timeout=POLL_TIMEOUT + 10) as client:
        while True:
            try:
                r = await client.get(
                    _url("getUpdates"),
                    params={"offset": offset, "timeout": POLL_TIMEOUT, "allowed_updates": '["message"]'},
                )
                if r.status_code == 409:
                    log.warning("Telegram getUpdates: 409, этого бота уже опрашивает другой процесс")
                if not r.is_success:
                    await asyncio.sleep(5)
                    continue
                updates = r.json()["result"]
            except (httpx.HTTPError, ValueError, KeyError) as e:
                log.warning("Telegram getUpdates: %s", type(e).__name__)
                await asyncio.sleep(5)
                continue

            for update in updates:
                offset = update["update_id"] + 1
                try:
                    await asyncio.to_thread(handle_update, update)
                except Exception:
                    log.exception("Не удалось обработать сообщение Telegram")
