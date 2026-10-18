import hashlib
import hmac
import os
import secrets

from fastapi import HTTPException, status

from src import config


def not_found(entity: str):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} not found")


def bad_request(detail: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest.hex(), digest_hex)


def new_email_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_email_code(user_id: int, code: str) -> str:
    # Код короткий, поэтому хэшируем с секретом: по утёкшей БД его не подобрать
    return hmac.new(config.JWT_SECRET.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def with_owner(own_ids: list[int], user_id: int) -> list[int]:
    # Текущий пользователь всегда остаётся среди владельцев
    ids = list(dict.fromkeys(own_ids))
    return ids if user_id in ids else [user_id, *ids]


def years_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "год"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "года"
    return "лет"


def new_telegram_code() -> str:
    # Параметр start в ссылке t.me допускает только A-Z a-z 0-9 _ - и до 64 символов
    return secrets.token_urlsafe(24)


def hash_telegram_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()
