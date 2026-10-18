from datetime import datetime

from pydantic import BaseModel, field_validator


class UserIn(BaseModel):
    email: str
    phone_number: str | None = None
    passwd: str
    name: str

    @field_validator("phone_number")
    @classmethod
    def empty_phone_is_none(cls, v: str | None) -> str | None:
        # Пустой номер = номера нет, иначе пустые строки упрутся в уникальность
        return (v.strip() or None) if v is not None else None


class User(BaseModel):
    id: int
    email: str
    phone_number: str | None
    name: str
    email_verified: bool
    telegram_linked: bool


class LoginIn(BaseModel):
    email: str
    passwd: str


class EmailIn(BaseModel):
    email: str


class EmailCodeIn(BaseModel):
    email: str
    code: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TelegramLink(BaseModel):
    url: str
    expires_in: int  # секунд


class PetIn(BaseModel):
    name: str
    type: str | None = None
    breed: str | None = None
    own_ids: list[int] = []
    prop_ids: list[int] = []


class Pet(PetIn):
    id: int


class PropIn(BaseModel):
    name: str
    msg: str | None = None
    text: str | None = None
    rep: bool = False
    date: datetime
    own_ids: list[int] = []


class Prop(PropIn):
    id: int
