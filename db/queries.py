from datetime import datetime

from psycopg import Connection

from db import db

USER_COLUMNS = "id, email, phone_number, name, email_verified, telegram_chat_id IS NOT NULL AS telegram_linked"
PET_COLUMNS = "id, name, type, breed, own_ids, prop_ids"
PROP_COLUMNS = "id, name, msg, text, rep, date, own_ids"


# ---------- проверки ----------

def _all_users_exist(conn: Connection, user_ids: list[int]) -> bool:
    row = conn.execute("SELECT count(*) AS n FROM users WHERE id = ANY(%s)", (user_ids,)).fetchone()
    return row["n"] == len(set(user_ids))


def _all_props_owned(conn: Connection, prop_ids: list[int], user_id: int) -> bool:
    row = conn.execute(
        "SELECT count(*) AS n FROM props WHERE id = ANY(%s) AND %s = ANY(own_ids)", (prop_ids, user_id)
    ).fetchone()
    return row["n"] == len(set(prop_ids))


class InvalidRefs(Exception):
    pass


def _check_refs(conn: Connection, user_id: int, own_ids: list[int], prop_ids: list[int] | None = None) -> None:
    if not _all_users_exist(conn, own_ids):
        raise InvalidRefs("Unknown user in own_ids")
    if prop_ids and not _all_props_owned(conn, prop_ids, user_id):
        raise InvalidRefs("Unknown prop in prop_ids")


# ---------- users ----------

def create_user(email: str, phone_number: str | None, passwd: str, name: str) -> dict:
    with db.pool.connection() as conn:
        return conn.execute(
            f"INSERT INTO users (email, phone_number, passwd, name) VALUES (%s, %s, %s, %s) RETURNING {USER_COLUMNS}",
            (email, phone_number, passwd, name),
        ).fetchone()


def get_user(user_id: int) -> dict | None:
    with db.pool.connection() as conn:
        return conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = %s", (user_id,)).fetchone()


def get_user_credentials(email: str) -> dict | None:
    with db.pool.connection() as conn:
        return conn.execute("SELECT id, passwd, email_verified FROM users WHERE email = %s", (email,)).fetchone()


def update_user(user_id: int, email: str, phone_number: str | None, passwd: str, name: str) -> dict | None:
    # Смена почты сбрасывает её подтверждение (справа от SET — старые значения строки)
    with db.pool.connection() as conn:
        return conn.execute(
            "UPDATE users SET email = %s, phone_number = %s, passwd = %s, name = %s, "
            f"email_verified = email_verified AND email = %s WHERE id = %s RETURNING {USER_COLUMNS}",
            (email, phone_number, passwd, name, email, user_id),
        ).fetchone()


def get_user_by_email(email: str) -> dict | None:
    with db.pool.connection() as conn:
        return conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE email = %s", (email,)).fetchone()


# ---------- коды подтверждения почты ----------

def save_email_code(user_id: int, code_hash: str, ttl_minutes: int, resend_seconds: int) -> bool:
    # Новый код заменяет старый, но не чаще раза в resend_seconds; False — если ещё рано
    with db.pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO email_codes (user_id, code_hash, expires_at)
            VALUES (%(user_id)s, %(code_hash)s, now() + make_interval(mins => %(ttl)s))
            ON CONFLICT (user_id) DO UPDATE
                SET code_hash = EXCLUDED.code_hash, expires_at = EXCLUDED.expires_at, sent_at = now(), attempts = 0
                WHERE email_codes.sent_at < now() - make_interval(secs => %(resend)s)
            RETURNING user_id
            """,
            {"user_id": user_id, "code_hash": code_hash, "ttl": ttl_minutes, "resend": resend_seconds},
        ).fetchone()
        return row is not None


def take_email_code_attempt(user_id: int, max_attempts: int) -> str | None:
    # Списываем попытку и отдаём хэш действующего кода; None — кода нет, истёк или попытки кончились
    with db.pool.connection() as conn:
        row = conn.execute(
            "UPDATE email_codes SET attempts = attempts + 1 "
            "WHERE user_id = %s AND attempts < %s AND expires_at > now() RETURNING code_hash",
            (user_id, max_attempts),
        ).fetchone()
        return row["code_hash"] if row else None


def mark_email_verified(user_id: int) -> None:
    with db.pool.connection() as conn:
        conn.execute("UPDATE users SET email_verified = TRUE WHERE id = %s", (user_id,))
        conn.execute("DELETE FROM email_codes WHERE user_id = %s", (user_id,))


# ---------- telegram ----------

def save_telegram_code(user_id: int, code_hash: str, ttl_minutes: int) -> None:
    # Новая ссылка заменяет старую
    with db.pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO telegram_link_codes (user_id, code_hash, expires_at)
            VALUES (%s, %s, now() + make_interval(mins => %s))
            ON CONFLICT (user_id) DO UPDATE SET code_hash = EXCLUDED.code_hash, expires_at = EXCLUDED.expires_at
            """,
            (user_id, code_hash, ttl_minutes),
        )


def link_telegram(code_hash: str, chat_id: int) -> bool:
    # Код одноразовый; один Telegram — один аккаунт, поэтому со старого аккаунта chat_id снимаем
    with db.pool.connection() as conn:
        row = conn.execute(
            "DELETE FROM telegram_link_codes WHERE code_hash = %s AND expires_at > now() RETURNING user_id", (code_hash,)
        ).fetchone()
        if row is None:
            return False
        conn.execute("UPDATE users SET telegram_chat_id = NULL WHERE telegram_chat_id = %s", (chat_id,))
        conn.execute("UPDATE users SET telegram_chat_id = %s WHERE id = %s", (chat_id, row["user_id"]))
        return True


def unlink_telegram(user_id: int) -> None:
    with db.pool.connection() as conn:
        conn.execute("UPDATE users SET telegram_chat_id = NULL WHERE id = %s", (user_id,))


def unlink_telegram_chat(chat_id: int) -> None:
    with db.pool.connection() as conn:
        conn.execute("UPDATE users SET telegram_chat_id = NULL WHERE telegram_chat_id = %s", (chat_id,))


def get_telegram_chats(user_ids: list[int]) -> list[int]:
    with db.pool.connection() as conn:
        rows = conn.execute(
            "SELECT telegram_chat_id FROM users WHERE id = ANY(%s) AND telegram_chat_id IS NOT NULL", (user_ids,)
        ).fetchall()
        return [r["telegram_chat_id"] for r in rows]


def delete_user(user_id: int) -> bool:
    # Убираем пользователя из владельцев; питомцы и записи без владельцев удаляются
    with db.pool.connection() as conn:
        deleted = conn.execute("DELETE FROM users WHERE id = %s", (user_id,)).rowcount
        conn.execute("UPDATE pets SET own_ids = array_remove(own_ids, %s) WHERE %s = ANY(own_ids)", (user_id, user_id))
        conn.execute("UPDATE props SET own_ids = array_remove(own_ids, %s) WHERE %s = ANY(own_ids)", (user_id, user_id))
        orphan_props = [r["id"] for r in conn.execute("DELETE FROM props WHERE own_ids = '{}' RETURNING id").fetchall()]
        if orphan_props:
            conn.execute(
                "UPDATE pets SET prop_ids = ARRAY(SELECT unnest(prop_ids) EXCEPT SELECT unnest(%s::bigint[])) WHERE prop_ids && %s::bigint[]",
                (orphan_props, orphan_props),
            )
        conn.execute("DELETE FROM pets WHERE own_ids = '{}'")
        return deleted > 0


# ---------- pets ----------

def create_pet(user_id: int, name: str, type: str | None, breed: str | None, own_ids: list[int], prop_ids: list[int]) -> dict:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids, prop_ids)
        return conn.execute(
            f"INSERT INTO pets (name, type, breed, own_ids, prop_ids) VALUES (%s, %s, %s, %s, %s) RETURNING {PET_COLUMNS}",
            (name, type, breed, own_ids, prop_ids),
        ).fetchone()


def get_pet(pet_id: int, user_id: int) -> dict | None:
    with db.pool.connection() as conn:
        return conn.execute(
            f"SELECT {PET_COLUMNS} FROM pets WHERE id = %s AND %s = ANY(own_ids)", (pet_id, user_id)
        ).fetchone()


def list_pets(user_id: int) -> list[dict]:
    with db.pool.connection() as conn:
        return conn.execute(
            f"SELECT {PET_COLUMNS} FROM pets WHERE %s = ANY(own_ids) ORDER BY id", (user_id,)
        ).fetchall()


def update_pet(pet_id: int, user_id: int, name: str, type: str | None, breed: str | None, own_ids: list[int], prop_ids: list[int]) -> dict | None:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids, prop_ids)
        return conn.execute(
            f"UPDATE pets SET name = %s, type = %s, breed = %s, own_ids = %s, prop_ids = %s WHERE id = %s AND %s = ANY(own_ids) RETURNING {PET_COLUMNS}",
            (name, type, breed, own_ids, prop_ids, pet_id, user_id),
        ).fetchone()


def delete_pet(pet_id: int, user_id: int) -> bool:
    with db.pool.connection() as conn:
        return conn.execute(
            "DELETE FROM pets WHERE id = %s AND %s = ANY(own_ids)", (pet_id, user_id)
        ).rowcount > 0


# ---------- props ----------

def create_prop(user_id: int, name: str, msg: str | None, text: str | None, rep: bool, date: datetime, own_ids: list[int]) -> dict:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids)
        return conn.execute(
            f"INSERT INTO props (name, msg, text, rep, date, own_ids) VALUES (%s, %s, %s, %s, %s, %s) RETURNING {PROP_COLUMNS}",
            (name, msg, text, rep, date, own_ids),
        ).fetchone()


def get_prop(prop_id: int, user_id: int) -> dict | None:
    with db.pool.connection() as conn:
        return conn.execute(
            f"SELECT {PROP_COLUMNS} FROM props WHERE id = %s AND %s = ANY(own_ids)", (prop_id, user_id)
        ).fetchone()


def list_props(user_id: int) -> list[dict]:
    with db.pool.connection() as conn:
        return conn.execute(
            f"SELECT {PROP_COLUMNS} FROM props WHERE %s = ANY(own_ids) ORDER BY date", (user_id,)
        ).fetchall()


def list_props_by_pet(pet_id: int, user_id: int) -> list[dict] | None:
    # Владелец питомца видит все его записи; None — питомца нет или он чужой
    with db.pool.connection() as conn:
        pet = conn.execute(
            "SELECT prop_ids FROM pets WHERE id = %s AND %s = ANY(own_ids)", (pet_id, user_id)
        ).fetchone()
        if pet is None:
            return None
        return conn.execute(
            f"SELECT {PROP_COLUMNS} FROM props WHERE id = ANY(%s) ORDER BY date", (pet["prop_ids"],)
        ).fetchall()


def update_prop(prop_id: int, user_id: int, name: str, msg: str | None, text: str | None, rep: bool, date: datetime, own_ids: list[int]) -> dict | None:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids)
        return conn.execute(
            f"UPDATE props SET name = %s, msg = %s, text = %s, rep = %s, date = %s, own_ids = %s WHERE id = %s AND %s = ANY(own_ids) RETURNING {PROP_COLUMNS}",
            (name, msg, text, rep, date, own_ids, prop_id, user_id),
        ).fetchone()


def delete_prop(prop_id: int, user_id: int) -> bool:
    # Убираем запись из питомцев в той же транзакции
    with db.pool.connection() as conn:
        deleted = conn.execute(
            "DELETE FROM props WHERE id = %s AND %s = ANY(own_ids)", (prop_id, user_id)
        ).rowcount
        if deleted:
            conn.execute("UPDATE pets SET prop_ids = array_remove(prop_ids, %s) WHERE %s = ANY(prop_ids)", (prop_id, prop_id))
        return deleted > 0
