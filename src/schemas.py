from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


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
# Свойства товаров, которые может рекомендовать врач (подписи — в src/recommendations.py)
DietTag = Literal[
    "hypoallergenic", "sensitive_digestion", "weight_control", "sterilised", "urinary", "renal", "dental",
    "joint", "hairball", "skin_coat", "long_coat", "brachycephalic", "active", "intellectual", "chewer",
]
Ingredient = Literal["chicken", "turkey", "beef", "lamb", "fish", "grain", "rice", "dairy"]


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
    # Только для category = "vet_visit": что врач рекомендовал и каких ингредиентов избегать
    diet_tags: list[DietTag] = []
    diet_exclude: list[Ingredient] = []

    @field_validator("reactions", "diet_tags", "diet_exclude")
    @classmethod
    def unique_items(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def food_fields_only_for_food(self):
        if self.category != "food" and (self.liked is not None or self.suitable is not None or self.reactions):
            raise ValueError("liked, suitable and reactions are only allowed for category food")
        if self.category != "vet_visit" and (self.diet_tags or self.diet_exclude):
            raise ValueError("diet_tags and diet_exclude are only allowed for category vet_visit")
        return self


class Prop(PropIn):
    id: int


class Notification(Prop):
    # prop — наступившая запись (id — это id записи), birthday — день рождения питомца (id = pet_id)
    kind: Literal["prop", "birthday"] = "prop"
    pet_id: int | None = None


class NotificationCount(BaseModel):
    count: int


class Recommendation(BaseModel):
    id: int
    kind: Literal["food", "toy", "accessory", "care"]
    name: str
    description: str | None
    tags: list[str]
    ingredients: list[str]
    score: int
    # Почему товар предложен: рекомендации врача, порода, история питания, возраст
    reasons: list[str]
