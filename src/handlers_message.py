from fastapi import APIRouter, Depends, Query, status

from db import queries
from src.auth import current_user_id
from src.handlers_community import member_community
from src.helpers import bad_request, forbidden, not_found
from src.schemas import Message, MessageIn

router = APIRouter(prefix="/message", tags=["message"])


# Читать и писать могут только участники сообщества.
# Менять сообщение может автор, удалять — автор или владелец сообщества

@router.post("/add", response_model=Message, status_code=status.HTTP_201_CREATED)
def message_add(community_id: int, message: MessageIn, user_id: int = Depends(current_user_id)):
    member_community(community_id, user_id)
    return queries.create_message(community_id, user_id, message.text)


@router.get("/list", response_model=list[Message])
def message_list(
    community_id: int,
    before_id: int | None = None,
    after_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    user_id: int = Depends(current_user_id),
):
    # Без курсоров — последние limit сообщений; before_id — история выше, after_id — новые
    if before_id is not None and after_id is not None:
        bad_request("Pass either before_id or after_id")
    member_community(community_id, user_id)
    return queries.list_messages(community_id, before_id, after_id, limit)


def message_access(message_id: int, user_id: int) -> dict:
    access = queries.get_message_access(message_id, user_id)
    if access is None:
        not_found("Message")
    return access


@router.put("/edit", response_model=Message)
def message_edit(message_id: int, message: MessageIn, user_id: int = Depends(current_user_id)):
    if message_access(message_id, user_id)["from_id"] != user_id:
        forbidden("Only the author can do this")
    updated = queries.update_message(message_id, user_id, message.text)
    if updated is None:
        not_found("Message")
    return updated


@router.delete("/del", status_code=status.HTTP_204_NO_CONTENT)
def message_del(message_id: int, user_id: int = Depends(current_user_id)):
    access = message_access(message_id, user_id)
    if user_id not in (access["from_id"], access["owner_id"]):
        forbidden("Only the author or the community owner can do this")
    if not queries.delete_message(message_id):
        not_found("Message")
