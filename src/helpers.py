import hashlib
import hmac
import os

from fastapi import HTTPException, status


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


def with_owner(own_ids: list[int], user_id: int) -> list[int]:
    # Текущий пользователь всегда остаётся среди владельцев
    ids = list(dict.fromkeys(own_ids))
    return ids if user_id in ids else [user_id, *ids]
