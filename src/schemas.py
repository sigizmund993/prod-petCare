from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, field_validator, model_validator


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
    has_picture: bool


# reminder — обычное напоминание; остальные — записи истории ухода
PropCategory = Literal["reminder", "food", "vaccination", "parasites", "vet_visit", "medication"]
# gi — проблемы с ЖКТ, allergy — аллергическая реакция
Reaction = Literal["gi", "allergy", "other"]


class PropIn(BaseModel):
    name: str
    msg: str | None = None
    text: str | None = None
    rep: bool = False
    date: datetime
    own_ids: list[int] = []
    category: PropCategory = "reminder"
    # Только для category = "food": понравилось, подошло (null — не оценено) и нежелательные реакции
    liked: bool | None = None
    suitable: bool | None = None
    reactions: list[Reaction] = []

    @field_validator("reactions")
    @classmethod
    def unique_reactions(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def food_fields_only_for_food(self):
        if self.category != "food" and (self.liked is not None or self.suitable is not None or self.reactions):
            raise ValueError("liked, suitable and reactions are only allowed for category food")
        return self


class Prop(PropIn):
    id: int


class Notification(Prop):
    # prop — наступившая запись (id — это id записи), birthday — день рождения питомца (id = pet_id)
    kind: Literal["prop", "birthday"] = "prop"
    pet_id: int | None = None


class NotificationCount(BaseModel):
    count: int


# Пробелы по краям обрезаются; пустая строка — 422
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
MessageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class CommunityIn(BaseModel):
    name: Name
    description: str | None = None


class Community(CommunityIn):
    id: int
    owner_id: int | None
    member_ids: list[int]
    created_at: datetime


class Member(BaseModel):
    # Публичная часть пользователя: почту и телефон другим участникам не показываем
    id: int
    name: str


class MessageIn(BaseModel):
    text: MessageText


class Message(MessageIn):
    id: int
    community_id: int
    # null — автор удалил аккаунт
    from_id: int | None
    from_name: str | None
    created_at: datetime
    edited_at: datetime | None
