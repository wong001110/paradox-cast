"""Lobby orchestration. Browsers propose changes; the server freezes the run manifest."""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_session
from .models import (
    CharacterCard,
    Lobby,
    LobbyInvitation,
    LobbyMember,
    LobbyRole,
    LobbyStatus,
    RunManifest,
    RuntimeProfile,
    Scenario,
    User,
    Visibility,
)
from .schemas import LobbyBindingUpdate, LobbyCreate, LobbyInviteCreate, LobbyJoin, LobbyReadyUpdate, ManifestStartRequest

router = APIRouter(prefix="/api/lobbies", tags=["lobbies"])


def require_user(user_id: str, session: Session) -> None:
    if not session.get(User, user_id):
        raise HTTPException(404, "user not found")


def member_view(member: LobbyMember) -> dict:
    return {"id": member.id, "user_id": member.user_id, "role": member.role.value, "cast_slot": member.cast_slot, "character_card_id": member.character_card_id, "runtime_profile_id": member.runtime_profile_id, "funding_model": member.funding_model.value, "ready": member.ready}


def manifest_view(manifest: RunManifest) -> dict:
    return {"id": manifest.id, "lobby_id": manifest.lobby_id, "scenario_version": manifest.scenario_version, "cast": manifest.cast, "runtime_bindings": manifest.runtime_bindings, "rules": manifest.rules, "seed": manifest.seed, "asset_versions": manifest.asset_versions, "intervention_rules": manifest.intervention_rules, "frozen_at": manifest.frozen_at.isoformat()}


def view(lobby: Lobby, session: Session, include_manifest: bool = True) -> dict:
    members = session.query(LobbyMember).filter_by(lobby_id=lobby.id).order_by(LobbyMember.joined_at).all()
    result = {"id": lobby.id, "host_id": lobby.host_id, "scenario_id": lobby.scenario_id, "join_code": lobby.join_code, "visibility": lobby.visibility.value, "status": lobby.status.value, "rules": lobby.rules, "members": [member_view(member) for member in members]}
    manifest = session.query(RunManifest).filter_by(lobby_id=lobby.id).one_or_none() if include_manifest else None
    if manifest:
        result["run_manifest"] = manifest_view(manifest)
    return result


def lobby_or_404(lobby_id: str, session: Session) -> Lobby:
    lobby = session.get(Lobby, lobby_id)
    if not lobby:
        raise HTTPException(404, "lobby not found")
    return lobby


def member_or_404(lobby_id: str, user_id: str, session: Session) -> LobbyMember:
    member = session.query(LobbyMember).filter_by(lobby_id=lobby_id, user_id=user_id).one_or_none()
    if not member:
        raise HTTPException(403, "not a lobby member")
    return member


def generate_join_code(session: Session) -> str:
    for _ in range(20):
        code = secrets.token_hex(4).upper()
        if not session.query(Lobby).filter_by(join_code=code).first():
            return code
    raise HTTPException(503, "could not allocate lobby code")


def join_lobby(lobby: Lobby, user_id: str, role: LobbyRole, session: Session) -> LobbyMember:
    require_user(user_id, session)
    if lobby.status is not LobbyStatus.OPEN:
        raise HTTPException(409, "lobby is no longer open")
    member = session.query(LobbyMember).filter_by(lobby_id=lobby.id, user_id=user_id).one_or_none()
    if member:
        return member
    member = LobbyMember(lobby_id=lobby.id, user_id=user_id, role=role)
    session.add(member)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "could not join lobby")
    session.refresh(member)
    return member


@router.post("", status_code=201)
def create(payload: LobbyCreate, owner_id: str, session: Session = Depends(get_session)) -> dict:
    require_user(owner_id, session)
    scenario = session.get(Scenario, payload.scenario_id)
    if not scenario or scenario.owner_id != owner_id:
        raise HTTPException(404, "scenario not found")
    lobby = Lobby(host_id=owner_id, scenario_id=scenario.id, join_code=generate_join_code(session), visibility=payload.visibility, rules=payload.rules)
    session.add(lobby)
    session.flush()
    session.add(LobbyMember(lobby_id=lobby.id, user_id=owner_id, role=LobbyRole.HOST))
    session.commit()
    session.refresh(lobby)
    return view(lobby, session)


@router.get("")
def browse_public(status: LobbyStatus = LobbyStatus.OPEN, session: Session = Depends(get_session)) -> list[dict]:
    lobbies = session.query(Lobby).filter_by(visibility=Visibility.PUBLIC, status=status).all()
    return [view(lobby, session, include_manifest=False) for lobby in lobbies]


@router.get("/join/{join_code}")
def lookup_join_link(join_code: str, session: Session = Depends(get_session)) -> dict:
    lobby = session.query(Lobby).filter_by(join_code=join_code.upper()).one_or_none()
    if not lobby:
        raise HTTPException(404, "lobby not found")
    return view(lobby, session, include_manifest=False)


@router.post("/join")
def join_by_code(payload: LobbyJoin, user_id: str, session: Session = Depends(get_session)) -> dict:
    lobby = session.query(Lobby).filter_by(join_code=payload.join_code.upper()).one_or_none()
    if not lobby:
        raise HTTPException(404, "lobby not found")
    join_lobby(lobby, user_id, payload.role, session)
    return view(lobby, session)


@router.get("/{lobby_id}")
def get_lobby(lobby_id: str, session: Session = Depends(get_session)) -> dict:
    return view(lobby_or_404(lobby_id, session), session)


@router.post("/{lobby_id}/join")
def join_by_link(lobby_id: str, payload: LobbyJoin, user_id: str, session: Session = Depends(get_session)) -> dict:
    lobby = lobby_or_404(lobby_id, session)
    if payload.join_code.upper() != lobby.join_code:
        raise HTTPException(403, "invalid join code")
    join_lobby(lobby, user_id, payload.role, session)
    return view(lobby, session)


@router.post("/{lobby_id}/invites", status_code=201)
def create_invite(lobby_id: str, payload: LobbyInviteCreate, owner_id: str, session: Session = Depends(get_session)) -> dict:
    lobby = lobby_or_404(lobby_id, session)
    if lobby.host_id != owner_id:
        raise HTTPException(403, "only the host can invite")
    if lobby.status is not LobbyStatus.OPEN:
        raise HTTPException(409, "lobby is no longer open")
    invitation = LobbyInvitation(lobby_id=lobby.id, token=secrets.token_urlsafe(18), created_by_id=owner_id, recipient_id=payload.recipient_id, role=payload.role)
    session.add(invitation)
    session.commit()
    return {"token": invitation.token, "lobby_id": lobby.id, "role": invitation.role.value, "recipient_id": invitation.recipient_id}


@router.post("/invites/{token}/accept")
def accept_invite(token: str, user_id: str, session: Session = Depends(get_session)) -> dict:
    invite = session.query(LobbyInvitation).filter_by(token=token).one_or_none()
    if not invite:
        raise HTTPException(404, "invitation not found")
    if invite.recipient_id and invite.recipient_id != user_id:
        raise HTTPException(403, "invitation belongs to another user")
    lobby = lobby_or_404(invite.lobby_id, session)
    join_lobby(lobby, user_id, invite.role, session)
    return view(lobby, session)


@router.put("/{lobby_id}/binding")
def set_binding(lobby_id: str, payload: LobbyBindingUpdate, user_id: str, session: Session = Depends(get_session)) -> dict:
    lobby = lobby_or_404(lobby_id, session)
    if lobby.status is not LobbyStatus.OPEN:
        raise HTTPException(409, "lobby is locked")
    member = member_or_404(lobby.id, user_id, session)
    if member.role is LobbyRole.SPECTATOR and (payload.character_card_id or payload.runtime_profile_id or payload.cast_slot):
        raise HTTPException(422, "spectators cannot bind a cast member")
    if payload.character_card_id:
        card = session.get(CharacterCard, payload.character_card_id)
        if not card or card.owner_id != user_id:
            raise HTTPException(404, "character card not found in your library")
    if payload.runtime_profile_id:
        runtime = session.get(RuntimeProfile, payload.runtime_profile_id)
        if not runtime or runtime.owner_id != user_id:
            raise HTTPException(404, "runtime profile not found")
    member.cast_slot = payload.cast_slot
    member.character_card_id = payload.character_card_id
    member.runtime_profile_id = payload.runtime_profile_id
    member.funding_model = payload.funding_model
    member.ready = False
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "that cast slot is already assigned")
    return view(lobby, session)


@router.put("/{lobby_id}/ready")
def set_ready(lobby_id: str, payload: LobbyReadyUpdate, user_id: str, session: Session = Depends(get_session)) -> dict:
    lobby = lobby_or_404(lobby_id, session)
    if lobby.status is not LobbyStatus.OPEN:
        raise HTTPException(409, "lobby is locked")
    member = member_or_404(lobby.id, user_id, session)
    if member.role is LobbyRole.SPECTATOR:
        raise HTTPException(422, "spectators do not participate in ready checks")
    if payload.ready and (not member.cast_slot or not member.character_card_id or not member.runtime_profile_id):
        raise HTTPException(422, "bind a cast slot, character, and runtime before readying")
    member.ready = payload.ready
    session.commit()
    return view(lobby, session)


@router.post("/{lobby_id}/start", status_code=201)
def lock_and_start(lobby_id: str, payload: ManifestStartRequest, owner_id: str, session: Session = Depends(get_session)) -> dict:
    lobby = lobby_or_404(lobby_id, session)
    if lobby.host_id != owner_id:
        raise HTTPException(403, "only the host can start")
    if lobby.status is not LobbyStatus.OPEN:
        raise HTTPException(409, "lobby has already been locked")
    if session.query(RunManifest).filter_by(lobby_id=lobby.id).one_or_none():
        raise HTTPException(409, "run manifest already exists")
    scenario = session.get(Scenario, lobby.scenario_id)
    members = session.query(LobbyMember).filter_by(lobby_id=lobby.id).all()
    players = [member for member in members if member.role is not LobbyRole.SPECTATOR]
    if not players or any(not member.ready for member in players):
        raise HTTPException(422, "all cast participants must be ready")

    cast: list[dict] = []
    bindings: list[dict] = []
    assets: dict[str, int] = {}
    for member in players:
        if not member.cast_slot or not member.character_card_id or not member.runtime_profile_id:
            raise HTTPException(422, "every participant needs a complete cast/runtime binding")
        card = session.get(CharacterCard, member.character_card_id)
        runtime = session.get(RuntimeProfile, member.runtime_profile_id)
        if not card or not runtime:
            raise HTTPException(422, "a selected cast or runtime was removed")
        cast.append({"slot": member.cast_slot, "user_id": member.user_id, "character_card_id": card.id, "character_version": card.version})
        bindings.append({"slot": member.cast_slot, "runtime_profile_id": runtime.id, "provider": runtime.provider, "model_id": runtime.model_id, "funding_model": member.funding_model.value})
        assets[f"character:{card.id}"] = card.version
    manifest = RunManifest(lobby_id=lobby.id, scenario_version=scenario.version, cast=cast, runtime_bindings=bindings, rules=lobby.rules, seed=payload.seed if payload.seed is not None else secrets.randbelow(2_147_483_647), asset_versions=assets, intervention_rules=payload.intervention_rules)
    session.add(manifest)
    lobby.status = LobbyStatus.RUNNING
    session.commit()
    session.refresh(manifest)
    return manifest_view(manifest)
