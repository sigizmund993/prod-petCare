from datetime import datetime

from psycopg import Connection

from db import db

USER_COLUMNS = "id, email, phone_number, name"
PET_COLUMNS = "id, name, own_ids, prop_ids"
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
        return conn.execute("SELECT id, passwd FROM users WHERE email = %s", (email,)).fetchone()


def update_user(user_id: int, email: str, phone_number: str | None, passwd: str, name: str) -> dict | None:
    with db.pool.connection() as conn:
        return conn.execute(
            f"UPDATE users SET email = %s, phone_number = %s, passwd = %s, name = %s WHERE id = %s RETURNING {USER_COLUMNS}",
            (email, phone_number, passwd, name, user_id),
        ).fetchone()


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

def create_pet(user_id: int, name: str, own_ids: list[int], prop_ids: list[int]) -> dict:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids, prop_ids)
        return conn.execute(
            f"INSERT INTO pets (name, own_ids, prop_ids) VALUES (%s, %s, %s) RETURNING {PET_COLUMNS}",
            (name, own_ids, prop_ids),
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


def update_pet(pet_id: int, user_id: int, name: str, own_ids: list[int], prop_ids: list[int]) -> dict | None:
    with db.pool.connection() as conn:
        _check_refs(conn, user_id, own_ids, prop_ids)
        return conn.execute(
            f"UPDATE pets SET name = %s, own_ids = %s, prop_ids = %s WHERE id = %s AND %s = ANY(own_ids) RETURNING {PET_COLUMNS}",
            (name, own_ids, prop_ids, pet_id, user_id),
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
