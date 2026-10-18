from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from db import queries
from src.auth import current_user_id
from src.helpers import bad_request, not_found
from src.recommendations import recommend, species_of
from src.schemas import Recommendation

router = APIRouter(prefix="/recommendation", tags=["recommendation"])

GOODS_KINDS = ["toy", "accessory", "care"]


def _recommend(pet_id: int, user_id: int, kinds: list[str], limit: int) -> list[dict]:
    pet = queries.get_pet(pet_id, user_id)
    if pet is None:
        not_found("Pet")
    species = species_of(pet["type"])
    if species is None:
        bad_request("Pet type must be cat or dog for recommendations")
    props = queries.list_props_by_pet(pet_id, user_id)
    breed = queries.find_breed(species, pet["breed"])
    return recommend(pet, queries.list_products(kinds), props, breed, date.today(), limit)


@router.get("/food", response_model=list[Recommendation])
def recommendation_food(pet_id: int, limit: int = Query(10, ge=1, le=50), user_id: int = Depends(current_user_id)):
    return _recommend(pet_id, user_id, ["food"], limit)


@router.get("/goods", response_model=list[Recommendation])
def recommendation_goods(
    pet_id: int,
    kind: Literal["toy", "accessory", "care"] | None = None,
    limit: int = Query(10, ge=1, le=50),
    user_id: int = Depends(current_user_id),
):
    # Игрушки, аксессуары и товары для ухода; kind — только один раздел
    return _recommend(pet_id, user_id, [kind] if kind else GOODS_KINDS, limit)
