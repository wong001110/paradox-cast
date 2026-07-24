"""Database-backed WebSocket snapshots for local and single-region lobby testing."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .database import SessionLocal
from .lobby_routes import view
from .models import Lobby, LobbyMember

router = APIRouter(tags=["lobbies"])


@router.websocket("/api/lobbies/{lobby_id}/ws")
async def lobby_socket(websocket: WebSocket, lobby_id: str, user_id: str) -> None:
    with SessionLocal() as session:
        lobby = session.get(Lobby, lobby_id)
        member = session.query(LobbyMember).filter_by(lobby_id=lobby_id, user_id=user_id).one_or_none()
        if not lobby or not member:
            await websocket.close(code=4403)
            return

    await websocket.accept()
    previous = ""
    try:
        while True:
            with SessionLocal() as session:
                lobby = session.get(Lobby, lobby_id)
                if not lobby:
                    await websocket.send_json({"type": "lobby.deleted", "lobby_id": lobby_id})
                    await websocket.close(code=4404)
                    return
                payload = view(lobby, session)
            serialized = json.dumps(payload, sort_keys=True, default=str)
            if serialized != previous:
                previous = serialized
                await websocket.send_json({"type": "lobby.updated", "lobby": payload})
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        return
