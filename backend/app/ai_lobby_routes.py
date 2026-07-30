"""Host-funded runtime binding for the usable local AI lobby flow."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_session
from .lobby_routes import lobby_or_404, member_or_404, view
from .models import CharacterCard, FundingModel, LobbyMember, LobbyRole, LobbyStatus, RuntimeProfile
from .schemas import LobbyBindingUpdate

router = APIRouter(prefix="/api/lobbies", tags=["AI lobby binding"])


@router.put("/{lobby_id}/ai-binding")
def set_host_funded_ai_binding(
    lobby_id: str,
    payload: LobbyBindingUpdate,
    user_id: str,
    session: Session = Depends(get_session),
) -> dict:
    lobby = lobby_or_404(lobby_id, session)
    if lobby.status is not LobbyStatus.OPEN:
        raise HTTPException(409, "lobby is locked")
    member = member_or_404(lobby.id, user_id, session)
    if member.role is LobbyRole.SPECTATOR:
        raise HTTPException(422, "spectators cannot bind a cast member")
    if not payload.cast_slot or not payload.character_card_id:
        raise HTTPException(422, "a cast slot and character card are required")

    card = session.get(CharacterCard, payload.character_card_id)
    if not card or card.owner_id != user_id:
        raise HTTPException(404, "character card not found in your library")

    runtime_id = payload.runtime_profile_id
    if user_id != lobby.host_id:
        host_member = (
            session.query(LobbyMember)
            .filter_by(lobby_id=lobby.id, user_id=lobby.host_id)
            .one_or_none()
        )
        runtime_id = host_member.runtime_profile_id if host_member else None
        if not runtime_id:
            raise HTTPException(422, "the host must bind an AI runtime first")

    runtime = session.get(RuntimeProfile, runtime_id) if runtime_id else None
    if not runtime or runtime.owner_id != lobby.host_id:
        raise HTTPException(404, "host AI runtime not found")

    member.cast_slot = payload.cast_slot
    member.character_card_id = card.id
    member.runtime_profile_id = runtime.id
    member.funding_model = FundingModel.HOST
    member.ready = False

    if user_id == lobby.host_id:
        shared_members = (
            session.query(LobbyMember)
            .filter_by(lobby_id=lobby.id, funding_model=FundingModel.HOST)
            .all()
        )
        for shared_member in shared_members:
            if shared_member.id == member.id:
                continue
            shared_member.runtime_profile_id = runtime.id
            shared_member.ready = False

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "that cast slot is already assigned")
    return view(lobby, session)
