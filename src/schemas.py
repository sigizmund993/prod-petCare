from datetime import date, datetime

from pydantic import BaseModel, field_validator


class UserIn(BaseModel):
    email: str
    phone_number: str | None = None
    passwd: str
    name: str


class User(BaseModel):
    id: int
    email: str
    phone_number: str | None
    name: str
    email_verified: bool


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


class PetIn(BaseModel):
    name: str
    type: str | None = None
    breed: str | None = None
    birth_date: date | None = None
    own_ids: list[int] = []
    prop_ids: list[int] = []

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_in_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("birth_date must not be in the future")
        return v


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


class NotificationCount(BaseModel):
    count: int
