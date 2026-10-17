from fastapi import APIRouter, Depends, status

from db import queries
from src.auth import current_user_id
from src.helpers import not_found
from src.schemas import NotificationCount, Prop

router = APIRouter(prefix="/notification", tags=["notification"])


@router.get("/list", response_model=list[Prop])
def notification_list(user_id: int = Depends(current_user_id)):
    return queries.list_notifications(user_id)


@router.get("/count", response_model=NotificationCount)
def notification_count(user_id: int = Depends(current_user_id)):
    return {"count": queries.count_notifications(user_id)}


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def notification_read(prop_id: int, user_id: int = Depends(current_user_id)):
    if not queries.read_notifications(user_id, prop_id):
        not_found("Notification")


@router.post("/read_all", status_code=status.HTTP_204_NO_CONTENT)
def notification_read_all(user_id: int = Depends(current_user_id)):
    queries.read_notifications(user_id)
