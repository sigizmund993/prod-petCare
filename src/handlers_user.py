import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from psycopg.errors import UniqueViolation

from db import queries
from src import config
from src.auth import create_token, current_user_id
from src.helpers import (
    hash_email_code,
    hash_password,
    hash_telegram_code,
    new_email_code,
    new_telegram_code,
    not_found,
    verify_password,
)
from src.mailer import send_mail
from src.schemas import EmailCodeIn, EmailIn, LoginIn, TelegramLink, Token, User, UserIn

router = APIRouter(prefix="/user", tags=["user"])


def already_taken(e: UniqueViolation):
    if e.diag.constraint_name == "users_phone_number_key":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")


def send_email_code(user_id: int, email: str, background_tasks: BackgroundTasks) -> None:
    # Код не отправляется повторно, если предыдущий ушёл меньше EMAIL_CODE_RESEND_SECONDS назад
    code = new_email_code()
    saved = queries.save_email_code(
        user_id, hash_email_code(user_id, code), config.EMAIL_CODE_TTL_MINUTES, config.EMAIL_CODE_RESEND_SECONDS
    )
    if saved:
        background_tasks.add_task(
            send_mail,
            email,
            "PetCare: код подтверждения почты",
            f"Ваш код подтверждения: {code}\n\nКод действует {config.EMAIL_CODE_TTL_MINUTES} минут.",
        )


@router.post("/add", response_model=User, status_code=status.HTTP_201_CREATED)
def user_add(user: UserIn, background_tasks: BackgroundTasks):
    try:
        created = queries.create_user(user.email, user.phone_number, hash_password(user.passwd), user.name)
    except UniqueViolation as e:
        already_taken(e)
    send_email_code(created["id"], created["email"], background_tasks)
    return created


@router.post("/verify", response_model=Token)
def user_verify(body: EmailCodeIn):
    user = queries.get_user_by_email(body.email)
    code_hash = queries.take_email_code_attempt(user["id"], config.EMAIL_CODE_MAX_ATTEMPTS) if user else None
    if code_hash is None or not hmac.compare_digest(code_hash, hash_email_code(user["id"], body.code.strip())):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong or expired code")
    queries.mark_email_verified(user["id"])
    return Token(access_token=create_token(user["id"]))


@router.post("/verify/resend", status_code=status.HTTP_204_NO_CONTENT)
def user_verify_resend(body: EmailIn, background_tasks: BackgroundTasks):
    # Ответ всегда 204, чтобы по нему нельзя было узнать, зарегистрирована ли почта
    user = queries.get_user_by_email(body.email)
    if user is not None and not user["email_verified"]:
        send_email_code(user["id"], user["email"], background_tasks)


@router.post("/login", response_model=Token)
def user_login(creds: LoginIn):
    user = queries.get_user_credentials(creds.email)
    if user is None or not verify_password(creds.passwd, user["passwd"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong email or password")
    if not user["email_verified"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")
    return Token(access_token=create_token(user["id"]))


@router.get("/me", response_model=User)
def user_me(user_id: int = Depends(current_user_id)):
    user = queries.get_user(user_id)
    if user is None:
        not_found("User")
    return user


@router.put("/edit", response_model=User)
def user_edit(user: UserIn, background_tasks: BackgroundTasks, user_id: int = Depends(current_user_id)):
    try:
        updated = queries.update_user(user_id, user.email, user.phone_number, hash_password(user.passwd), user.name)
    except UniqueViolation as e:
        already_taken(e)
    if updated is None:
        not_found("User")
    if not updated["email_verified"]:
        send_email_code(user_id, updated["email"], background_tasks)
    return updated


@router.delete("/del", status_code=status.HTTP_204_NO_CONTENT)
def user_del(user_id: int = Depends(current_user_id)):
    if not queries.delete_user(user_id):
        not_found("User")


@router.post("/telegram/link", response_model=TelegramLink)
def user_telegram_link(user_id: int = Depends(current_user_id)):
    # Ссылка на бота с одноразовым кодом: по Start бот узнаёт chat_id и привязывает его к аккаунту
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_BOT_USERNAME:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram is not configured")
    code = new_telegram_code()
    queries.save_telegram_code(user_id, hash_telegram_code(code), config.TELEGRAM_LINK_TTL_MINUTES)
    return TelegramLink(
        url=f"https://t.me/{config.TELEGRAM_BOT_USERNAME}?start={code}",
        expires_in=config.TELEGRAM_LINK_TTL_MINUTES * 60,
    )


@router.delete("/telegram", status_code=status.HTTP_204_NO_CONTENT)
def user_telegram_unlink(user_id: int = Depends(current_user_id)):
    queries.unlink_telegram(user_id)
