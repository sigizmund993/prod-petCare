from datetime import datetime

from pydantic import BaseModel


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


class LoginIn(BaseModel):
    email: str
    passwd: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PetIn(BaseModel):
    name: str
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
