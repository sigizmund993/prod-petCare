from fastapi import APIRouter, Depends, status

from db import queries
from src import config
from src.auth import current_user_id
from src.helpers import bad_request, not_found, years_word
from src.schemas import Notification, NotificationCount

router = APIRouter(prefix="/notification", tags=["notification"])


def birthday_notification(pet: dict) -> dict:
    return {
        "kind": "birthday",
        "id": pet["id"],
        "pet_id": pet["id"],
        "name": f"День рождения: {pet['name']}",
        "msg": f"Исполняется {pet['years']} {years_word(pet['years'])}",
        "text": None,
        "rep": True,
        "date": pet["date"],
        "own_ids": pet["own_ids"],
    }


@router.get("/list", response_model=list[Notification])
def notification_list(user_id: int = Depends(current_user_id)):
    birthdays = [birthday_notification(p) for p in queries.list_birthdays(user_id, config.TIMEZONE)]
    return sorted(birthdays + queries.list_notifications(user_id), key=lambda n: n["date"], reverse=True)


@router.get("/count", response_model=NotificationCount)
def notification_count(user_id: int = Depends(current_user_id)):
    return {"count": queries.count_notifications(user_id, config.TIMEZONE)}


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def notification_read(prop_id: int | None = None, pet_id: int | None = None, user_id: int = Depends(current_user_id)):
    # prop_id — уведомление о записи, pet_id — о дне рождения питомца
    if (prop_id is None) == (pet_id is None):
        bad_request("Pass either prop_id or pet_id")
    if prop_id is not None:
        read = queries.read_notifications(user_id, prop_id)
    else:
        read = queries.read_birthdays(user_id, config.TIMEZONE, pet_id)
    if not read:
        not_found("Notification")


@router.post("/read_all", status_code=status.HTTP_204_NO_CONTENT)
def notification_read_all(user_id: int = Depends(current_user_id)):
    queries.read_notifications(user_id)
    queries.read_birthdays(user_id, config.TIMEZONE)
