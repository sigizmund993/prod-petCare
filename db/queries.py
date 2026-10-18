from datetime import date, datetime

from psycopg import Connection

from db import db

USER_COLUMNS = "id, email, phone_number, name, email_verified"
PET_COLUMNS = "id, name, type, breed, birth_date, own_ids, prop_ids, picture IS NOT NULL AS has_picture"
PROP_COLUMNS = "id, name, msg, text, rep, date, own_ids, category, liked, suitable, reactions, diet_tags, diet_exclude"


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

def create_pet(user_id: int, name: str, type: str | None, breed: str | None, birth_date: date | None, own_ids: list[int], prop_ids: list[int]) -> dict:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids, prop_ids)
        return conn.execute(
            f"INSERT INTO pets (name, type, breed, birth_date, own_ids, prop_ids) VALUES (%s, %s, %s, %s, %s, %s) RETURNING {PET_COLUMNS}",
            (name, type, breed, birth_date, own_ids, prop_ids),
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


def update_pet(pet_id: int, user_id: int, name: str, type: str | None, breed: str | None, birth_date: date | None, own_ids: list[int], prop_ids: list[int]) -> dict | None:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids, prop_ids)
        return conn.execute(
            f"UPDATE pets SET name = %s, type = %s, breed = %s, birth_date = %s, own_ids = %s, prop_ids = %s WHERE id = %s AND %s = ANY(own_ids) RETURNING {PET_COLUMNS}",
            (name, type, breed, birth_date, own_ids, prop_ids, pet_id, user_id),
        ).fetchone()


def set_pet_picture(pet_id: int, user_id: int, picture: bytes | None, picture_type: str | None) -> bool:
    # picture=None удаляет картинку; False — питомца нет или он чужой
    with db.pool.connection() as conn:
        return conn.execute(
            "UPDATE pets SET picture = %s, picture_type = %s WHERE id = %s AND %s = ANY(own_ids)",
            (picture, picture_type, pet_id, user_id),
        ).rowcount > 0


def get_pet_picture(pet_id: int, user_id: int) -> dict | None:
    with db.pool.connection() as conn:
        return conn.execute(
            "SELECT picture, picture_type FROM pets WHERE id = %s AND %s = ANY(own_ids) AND picture IS NOT NULL",
            (pet_id, user_id),
        ).fetchone()


def delete_pet(pet_id: int, user_id: int) -> bool:
    with db.pool.connection() as conn:
        return conn.execute(
            "DELETE FROM pets WHERE id = %s AND %s = ANY(own_ids)", (pet_id, user_id)
        ).rowcount > 0


# ---------- props ----------

def create_prop(user_id: int, name: str, msg: str | None, text: str | None, rep: bool, date: datetime, own_ids: list[int],
                category: str, liked: bool | None, suitable: bool | None, reactions: list[str],
                diet_tags: list[str], diet_exclude: list[str]) -> dict:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids)
        return conn.execute(
            "INSERT INTO props (name, msg, text, rep, date, own_ids, category, liked, suitable, reactions, diet_tags, diet_exclude) "
            f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING {PROP_COLUMNS}",
            (name, msg, text, rep, date, own_ids, category, liked, suitable, reactions, diet_tags, diet_exclude),
        ).fetchone()


def get_prop(prop_id: int, user_id: int) -> dict | None:
    with db.pool.connection() as conn:
        return conn.execute(
            f"SELECT {PROP_COLUMNS} FROM props WHERE id = %s AND %s = ANY(own_ids)", (prop_id, user_id)
        ).fetchone()


# Необязательные фильтры списка записей: None — не фильтровать
_PROP_FILTERS = (
    "(%(category)s::text IS NULL OR category = %(category)s) "
    "AND (%(liked)s::boolean IS NULL OR liked = %(liked)s) "
    "AND (%(suitable)s::boolean IS NULL OR suitable = %(suitable)s)"
)


def list_props(user_id: int, category: str | None = None, liked: bool | None = None, suitable: bool | None = None) -> list[dict]:
    with db.pool.connection() as conn:
        return conn.execute(
            f"SELECT {PROP_COLUMNS} FROM props WHERE %(user_id)s = ANY(own_ids) AND {_PROP_FILTERS} ORDER BY date",
            {"user_id": user_id, "category": category, "liked": liked, "suitable": suitable},
        ).fetchall()


def list_props_by_pet(pet_id: int, user_id: int, category: str | None = None, liked: bool | None = None,
                      suitable: bool | None = None) -> list[dict] | None:
    # Владелец питомца видит все его записи; None — питомца нет или он чужой
    with db.pool.connection() as conn:
        pet = conn.execute(
            "SELECT prop_ids FROM pets WHERE id = %s AND %s = ANY(own_ids)", (pet_id, user_id)
        ).fetchone()
        if pet is None:
            return None
        return conn.execute(
            f"SELECT {PROP_COLUMNS} FROM props WHERE id = ANY(%(ids)s) AND {_PROP_FILTERS} ORDER BY date",
            {"ids": pet["prop_ids"], "category": category, "liked": liked, "suitable": suitable},
        ).fetchall()


def update_prop(prop_id: int, user_id: int, name: str, msg: str | None, text: str | None, rep: bool, date: datetime, own_ids: list[int],
                category: str, liked: bool | None, suitable: bool | None, reactions: list[str],
                diet_tags: list[str], diet_exclude: list[str]) -> dict | None:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids)
        return conn.execute(
            "UPDATE props SET name = %s, msg = %s, text = %s, rep = %s, date = %s, own_ids = %s, "
            "category = %s, liked = %s, suitable = %s, reactions = %s, diet_tags = %s, diet_exclude = %s "
            f"WHERE id = %s AND %s = ANY(own_ids) RETURNING {PROP_COLUMNS}",
            (name, msg, text, rep, date, own_ids, category, liked, suitable, reactions, diet_tags, diet_exclude, prop_id, user_id),
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


# ---------- уведомления ----------

# Последнее наступившее срабатывание записи: повторяющиеся срабатывают каждый день начиная с date
_OCCURRENCE = (
    "CASE WHEN p.rep AND p.date <= now() "
    "THEN p.date + make_interval(days => floor(extract(epoch FROM now() - p.date) / 86400)::int) "
    "ELSE p.date END"
)

_DUE_PROPS = f"""
    SELECT p.id, p.name, p.msg, p.text, p.rep, {_OCCURRENCE} AS date, p.own_ids,
           p.category, p.liked, p.suitable, p.reactions, p.diet_tags, p.diet_exclude
    FROM props p
    LEFT JOIN notification_reads r ON r.prop_id = p.id AND r.user_id = %(user_id)s
    -- Записи о кормах — история питания, а не напоминания
    WHERE %(user_id)s = ANY(p.own_ids) AND p.date <= now() AND p.category <> 'food'
      AND (r.read_date IS NULL OR r.read_date < {_OCCURRENCE})
"""


# День рождения в этом году (29 февраля в невисокосный год становится 28-м); today — дата в часовом поясе %(tz)s
_BIRTHDAYS = """
    SELECT p.id, p.name, p.own_ids, y.years, b.day,
           b.day::timestamp AT TIME ZONE %(tz)s AS date
    FROM pets p
    CROSS JOIN (SELECT (now() AT TIME ZONE %(tz)s)::date AS today) t
    CROSS JOIN LATERAL (SELECT (extract(year FROM t.today) - extract(year FROM p.birth_date))::int AS years) y
    CROSS JOIN LATERAL (SELECT (p.birth_date + make_interval(years => y.years))::date AS day) b
    LEFT JOIN birthday_reads r ON r.pet_id = p.id AND r.user_id = %(user_id)s
    WHERE %(user_id)s = ANY(p.own_ids) AND y.years >= 1 AND b.day = t.today
      AND (r.read_date IS NULL OR r.read_date < b.day)
"""


def list_notifications(user_id: int) -> list[dict]:
    with db.pool.connection() as conn:
        return conn.execute(f"{_DUE_PROPS} ORDER BY date DESC", {"user_id": user_id}).fetchall()


def list_birthdays(user_id: int, tz: str) -> list[dict]:
    with db.pool.connection() as conn:
        return conn.execute(f"{_BIRTHDAYS} ORDER BY p.id", {"user_id": user_id, "tz": tz}).fetchall()


def count_notifications(user_id: int, tz: str) -> int:
    with db.pool.connection() as conn:
        return conn.execute(
            f"SELECT (SELECT count(*) FROM ({_DUE_PROPS}) d) + (SELECT count(*) FROM ({_BIRTHDAYS}) b) AS n",
            {"user_id": user_id, "tz": tz},
        ).fetchone()["n"]


def read_notifications(user_id: int, prop_id: int | None = None) -> int:
    # Отмечает прочитанными наступившие уведомления (одно или все); возвращает их количество
    with db.pool.connection() as conn:
        return conn.execute(
            f"""
            INSERT INTO notification_reads (user_id, prop_id, read_date)
            SELECT %(user_id)s, id, date FROM ({_DUE_PROPS}) due
            WHERE %(prop_id)s::bigint IS NULL OR id = %(prop_id)s
            ON CONFLICT (user_id, prop_id) DO UPDATE SET read_date = EXCLUDED.read_date
            """,
            {"user_id": user_id, "prop_id": prop_id},
        ).rowcount


def read_birthdays(user_id: int, tz: str, pet_id: int | None = None) -> int:
    with db.pool.connection() as conn:
        return conn.execute(
            f"""
            INSERT INTO birthday_reads (user_id, pet_id, read_date)
            SELECT %(user_id)s, id, day FROM ({_BIRTHDAYS}) due
            WHERE %(pet_id)s::bigint IS NULL OR id = %(pet_id)s
            ON CONFLICT (user_id, pet_id) DO UPDATE SET read_date = EXCLUDED.read_date
            """,
            {"user_id": user_id, "tz": tz, "pet_id": pet_id},
        ).rowcount


# ---------- рекомендации ----------

PRODUCT_COLUMNS = "id, kind, name, description, species, age_groups, sizes, tags, ingredients"


def find_breed(species: str, breed: str | None) -> dict | None:
    if not breed:
        return None
    with db.pool.connection() as conn:
        return conn.execute(
            "SELECT name, size, tags FROM breeds WHERE species = %s AND %s = ANY(names)", (species, breed.strip().lower())
        ).fetchone()


def list_products(kinds: list[str]) -> list[dict]:
    with db.pool.connection() as conn:
        return conn.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE kind = ANY(%s) ORDER BY id", (kinds,)).fetchall()
