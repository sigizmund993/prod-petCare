from fastapi import APIRouter, Depends, status

from db import queries
from src.auth import current_user_id
from src.helpers import bad_request, not_found, with_owner
from src.schemas import Prop, PropCategory, PropIn

router = APIRouter(prefix="/prop", tags=["prop"])


@router.post("/add", response_model=Prop, status_code=status.HTTP_201_CREATED)
def prop_add(prop: PropIn, user_id: int = Depends(current_user_id)):
    try:
        return queries.create_prop(
            user_id, prop.name, prop.msg, prop.text, prop.rep, prop.date, with_owner(prop.own_ids, user_id),
            prop.category, prop.liked, prop.suitable, prop.reactions,
        )
    except queries.InvalidRefs as e:
        bad_request(str(e))


@router.delete("/del", status_code=status.HTTP_204_NO_CONTENT)
def prop_del(prop_id: int, user_id: int = Depends(current_user_id)):
    if not queries.delete_prop(prop_id, user_id):
        not_found("Prop")


@router.put("/edit", response_model=Prop)
def prop_edit(prop_id: int, prop: PropIn, user_id: int = Depends(current_user_id)):
    try:
        updated = queries.update_prop(
            prop_id, user_id, prop.name, prop.msg, prop.text, prop.rep, prop.date, with_owner(prop.own_ids, user_id),
            prop.category, prop.liked, prop.suitable, prop.reactions,
        )
    except queries.InvalidRefs as e:
        bad_request(str(e))
    if updated is None:
        not_found("Prop")
    return updated


@router.get("/get", response_model=Prop)
def prop_get(prop_id: int, user_id: int = Depends(current_user_id)):
    prop = queries.get_prop(prop_id, user_id)
    if prop is None:
        not_found("Prop")
    return prop


@router.get("/list", response_model=list[Prop])
def prop_list(
    pet_id: int | None = None,
    category: PropCategory | None = None,
    liked: bool | None = None,
    suitable: bool | None = None,
    user_id: int = Depends(current_user_id),
):
    # Например, корма, которые подошли питомцу: ?pet_id=1&category=food&suitable=true
    if pet_id is None:
        return queries.list_props(user_id, category, liked, suitable)
    props = queries.list_props_by_pet(pet_id, user_id, category, liked, suitable)
    if props is None:
        not_found("Pet")
    return props
