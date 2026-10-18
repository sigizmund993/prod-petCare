import asyncio
import logging
from zoneinfo import ZoneInfo

import httpx

from db import queries
from src import config
from src.helpers import hash_telegram_code

log = logging.getLogger("uvicorn.error")

POLL_TIMEOUT = 30  # секунд, long polling


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


def notify_new_prop(prop: dict) -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        return
    date = prop["date"].astimezone(ZoneInfo(config.TIMEZONE)).strftime("%d.%m.%Y %H:%M")
    lines = [f"🐾 Новая запись: {prop['name']}", f"📅 {date}"]
    if prop["msg"]:
        lines.append(prop["msg"])
    if prop["text"]:
        lines.append(prop["text"])
    text = "\n".join(lines)
    for chat_id in queries.get_telegram_chats(prop["own_ids"]):
        send_message(chat_id, text)


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
