from fastapi import APIRouter, Depends, status

from db import queries
from src.auth import current_user_id
from src.helpers import bad_request, not_found, with_owner
from src.schemas import Pet, PetIn

router = APIRouter(prefix="/pet", tags=["pet"])


@router.post("/add", response_model=Pet, status_code=status.HTTP_201_CREATED)
def pet_add(pet: PetIn, user_id: int = Depends(current_user_id)):
    try:
        return queries.create_pet(user_id, pet.name, pet.type, pet.breed, pet.birth_date, with_owner(pet.own_ids, user_id), pet.prop_ids)
    except queries.InvalidRefs as e:
        bad_request(str(e))


@router.delete("/del", status_code=status.HTTP_204_NO_CONTENT)
def pet_del(pet_id: int, user_id: int = Depends(current_user_id)):
    if not queries.delete_pet(pet_id, user_id):
        not_found("Pet")


@router.put("/edit", response_model=Pet)
def pet_edit(pet_id: int, pet: PetIn, user_id: int = Depends(current_user_id)):
    try:
        updated = queries.update_pet(pet_id, user_id, pet.name, pet.type, pet.breed, pet.birth_date, with_owner(pet.own_ids, user_id), pet.prop_ids)
    except queries.InvalidRefs as e:
        bad_request(str(e))
    if updated is None:
        not_found("Pet")
    return updated


@router.get("/get", response_model=Pet)
def pet_get(pet_id: int, user_id: int = Depends(current_user_id)):
    pet = queries.get_pet(pet_id, user_id)
    if pet is None:
        not_found("Pet")
    return pet


@router.get("/list", response_model=list[Pet])
def pet_list(user_id: int = Depends(current_user_id)):
    return queries.list_pets(user_id)
