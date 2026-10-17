from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import UniqueViolation

from db import queries
from src.auth import create_token, current_user_id
from src.helpers import hash_password, not_found, verify_password
from src.schemas import LoginIn, Token, User, UserIn

router = APIRouter(prefix="/user", tags=["user"])


def email_taken():
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")


@router.post("/add", response_model=User, status_code=status.HTTP_201_CREATED)
def user_add(user: UserIn):
    try:
        return queries.create_user(user.email, user.phone_number, hash_password(user.passwd), user.name)
    except UniqueViolation:
        email_taken()


@router.post("/login", response_model=Token)
def user_login(creds: LoginIn):
    user = queries.get_user_credentials(creds.email)
    if user is None or not verify_password(creds.passwd, user["passwd"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong email or password")
    return Token(access_token=create_token(user["id"]))


@router.get("/me", response_model=User)
def user_me(user_id: int = Depends(current_user_id)):
    user = queries.get_user(user_id)
    if user is None:
        not_found("User")
    return user


@router.put("/edit", response_model=User)
def user_edit(user: UserIn, user_id: int = Depends(current_user_id)):
    try:
        updated = queries.update_user(user_id, user.email, user.phone_number, hash_password(user.passwd), user.name)
    except UniqueViolation:
        email_taken()
    if updated is None:
        not_found("User")
    return updated


@router.delete("/del", status_code=status.HTTP_204_NO_CONTENT)
def user_del(user_id: int = Depends(current_user_id)):
    if not queries.delete_user(user_id):
        not_found("User")
