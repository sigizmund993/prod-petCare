from fastapi import APIRouter, Depends, status

from db import queries
from src.auth import current_user_id
from src.helpers import bad_request, forbidden, not_found
from src.schemas import Community, CommunityIn, Member

router = APIRouter(prefix="/community", tags=["community"])


# Сообщества открытые: смотреть и вступать может любой, менять и выгонять — только владелец

def community_or_404(community_id: int) -> dict:
    community = queries.get_community(community_id)
    if community is None:
        not_found("Community")
    return community


def owned_community(community_id: int, user_id: int) -> dict:
    community = community_or_404(community_id)
    if community["owner_id"] != user_id:
        forbidden("Only the owner can do this")
    return community


def member_community(community_id: int, user_id: int) -> dict:
    community = community_or_404(community_id)
    if user_id not in community["member_ids"]:
        forbidden("Not a member")
    return community


@router.post("/add", response_model=Community, status_code=status.HTTP_201_CREATED)
def community_add(community: CommunityIn, user_id: int = Depends(current_user_id)):
    return queries.create_community(user_id, community.name, community.description)


@router.get("/list", response_model=list[Community])
def community_list(q: str | None = None, mine: bool = False, user_id: int = Depends(current_user_id)):
    return queries.list_communities(user_id, (q or "").strip() or None, mine)


@router.get("/get", response_model=Community)
def community_get(community_id: int, user_id: int = Depends(current_user_id)):
    return community_or_404(community_id)


@router.put("/edit", response_model=Community)
def community_edit(community_id: int, community: CommunityIn, user_id: int = Depends(current_user_id)):
    owned_community(community_id, user_id)
    updated = queries.update_community(community_id, user_id, community.name, community.description)
    if updated is None:
        not_found("Community")
    return updated


@router.delete("/del", status_code=status.HTTP_204_NO_CONTENT)
def community_del(community_id: int, user_id: int = Depends(current_user_id)):
    owned_community(community_id, user_id)
    if not queries.delete_community(community_id, user_id):
        not_found("Community")


@router.post("/join", response_model=Community)
def community_join(community_id: int, user_id: int = Depends(current_user_id)):
    community = queries.join_community(community_id, user_id)
    if community is None:
        not_found("Community")
    return community


@router.post("/leave", status_code=status.HTTP_204_NO_CONTENT)
def community_leave(community_id: int, user_id: int = Depends(current_user_id)):
    member_community(community_id, user_id)
    queries.remove_member(community_id, user_id)


@router.post("/kick", status_code=status.HTTP_204_NO_CONTENT)
def community_kick(community_id: int, member_id: int, user_id: int = Depends(current_user_id)):
    community = owned_community(community_id, user_id)
    if member_id == user_id:
        bad_request("Owner cannot kick themselves, use /community/leave")
    if member_id not in community["member_ids"]:
        not_found("Member")
    queries.remove_member(community_id, member_id)


@router.get("/members", response_model=list[Member])
def community_members(community_id: int, user_id: int = Depends(current_user_id)):
    community_or_404(community_id)
    return queries.list_members(community_id)
