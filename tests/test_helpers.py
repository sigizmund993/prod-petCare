from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src import config
from src.auth import create_token, current_user_id
from src.helpers import hash_email_code, hash_password, new_email_code, verify_password, with_owner, years_word


def test_password_hash_roundtrip():
    stored = hash_password("secret")
    assert "secret" not in stored
    assert verify_password("secret", stored)
    assert not verify_password("Secret", stored)


def test_password_hash_is_salted():
    assert hash_password("secret") != hash_password("secret")


def test_email_code_is_six_digits():
    for _ in range(50):
        code = new_email_code()
        assert len(code) == 6 and code.isdigit()


def test_email_code_hash_depends_on_user():
    assert hash_email_code(1, "123456") != hash_email_code(2, "123456")
    assert hash_email_code(1, "123456") == hash_email_code(1, "123456")


@pytest.mark.parametrize(
    "own_ids, user_id, expected",
    [
        ([], 1, [1]),
        ([2, 3], 1, [1, 2, 3]),
        ([2, 1], 1, [2, 1]),
        ([2, 2, 3, 2], 1, [1, 2, 3]),
    ],
)
def test_with_owner(own_ids, user_id, expected):
    assert with_owner(own_ids, user_id) == expected


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_token_roundtrip():
    assert current_user_id(_bearer(create_token(42))) == 42


def test_expired_token_rejected():
    token = jwt.encode({"sub": "42", "exp": datetime.now(UTC) - timedelta(seconds=1)}, config.JWT_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as e:
        current_user_id(_bearer(token))
    assert e.value.status_code == 401


def test_token_with_wrong_secret_rejected():
    token = jwt.encode({"sub": "42", "exp": datetime.now(UTC) + timedelta(hours=1)}, "another-secret-that-is-long-enough-too", algorithm="HS256")
    with pytest.raises(HTTPException):
        current_user_id(_bearer(token))


@pytest.mark.parametrize(
    "n, word",
    [(1, "год"), (2, "года"), (4, "года"), (5, "лет"), (11, "лет"), (12, "лет"), (14, "лет"), (21, "год"), (22, "года"), (25, "лет"), (111, "лет")],
)
def test_years_word(n, word):
    assert years_word(n) == word
