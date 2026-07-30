from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .ai_run import AIRunConfigurationError, run_manifest_with_ai
from .database import get_session
from .models import Lobby, LobbyStatus, RunManifest
from .runtime_service import RuntimeProviderError

router = APIRouter(prefix="/api/lobbies", tags=["AI runs"])


@router.post("/{lobby_id}/run-ai")
def run_ai_manifest(
    lobby_id: str,
    owner_id: str,
    turns: int = Query(default=2, ge=1, le=4),
    allow_fallback: bool = True,
    session: Session = Depends(get_session),
) -> dict:
    lobby = session.get(Lobby, lobby_id)
    if not lobby:
        raise HTTPException(404, "lobby not found")
    if lobby.host_id != owner_id:
        raise HTTPException(403, "only the host can run the frozen manifest")
    if lobby.status is not LobbyStatus.RUNNING:
        raise HTTPException(409, "lock the run manifest before starting an AI run")
    manifest = session.query(RunManifest).filter_by(lobby_id=lobby.id).one_or_none()
    if not manifest:
        raise HTTPException(409, "run manifest is not locked")
    try:
        return run_manifest_with_ai(
            session,
            manifest,
            turns=turns,
            allow_fallback=allow_fallback,
        )
    except AIRunConfigurationError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeProviderError as error:
        raise HTTPException(502, str(error)) from error
