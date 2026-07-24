"""A self-contained, truthful end-to-end demo for local product testing.

It exercises the same persisted CharacterCard, Scenario, Lobby and RunManifest
models used by the regular APIs, then asks the authoritative kernel for both
the original and an explainably branched replay.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .branching import branch, divergence
from .database import get_session
from .models import CharacterCard, FundingModel, Lobby, LobbyMember, LobbyRole, LobbyStatus, RunManifest, RuntimeProfile, Scenario, User, Visibility
from .schemas import SimulationRequest
from .simulation import simulate

router = APIRouter(prefix="/api/demo", tags=["demo"])

CAST = [
    ("hana", "Hana", 23, {"values": ["care", "truth"], "style": "warm observer"}),
    ("rei", "Rei", 25, {"values": ["logic", "evidence"], "style": "careful reasoner"}),
    ("mira", "Mira", 21, {"values": ["freedom", "curiosity"], "style": "playful disruptor"}),
]


def _get_or_create(session: Session, model: type, defaults: dict, **filters):
    item = session.query(model).filter_by(**filters).one_or_none()
    if item:
        return item
    item = model(**filters, **defaults)
    session.add(item)
    session.flush()
    return item


@router.post("/run")
def run_demo(session: Session = Depends(get_session)) -> dict:
    director = _get_or_create(session, User, {"is_admin": True}, display_name="Demo Director")
    scenario = _get_or_create(
        session,
        Scenario,
        {"synopsis": "A spring festival disappearance leaves a timeline fragment behind.", "world": {"tone": "everyday mystery"}, "visibility": Visibility.PUBLIC},
        owner_id=director.id,
        title="The Vanishing of April 14th",
    )
    runtime = _get_or_create(
        session,
        RuntimeProfile,
        {"provider": "mock", "model_id": "deterministic-v1", "temperature": 0.2, "max_tokens": 300, "timeout_seconds": 10, "retry_count": 0, "supports_structured_output": True},
        owner_id=director.id,
        display_name="Deterministic Demo Runtime",
    )
    cards: dict[str, CharacterCard] = {}
    cast_users: dict[str, User] = {}
    for index, (key, name, age, profile) in enumerate(CAST, 1):
        cast_users[key] = director if index == 1 else _get_or_create(session, User, {}, display_name=f"Demo {name} Player")
        cards[key] = _get_or_create(
            session,
            CharacterCard,
            {"biography": f"{name} is part of the official adult default cast.", "profile": profile, "visual_assets": {"reference": "official/v1/default-cast-contact-sheet"}, "visibility": Visibility.PUBLIC},
            owner_id=cast_users[key].id,
            name=name,
            adult_age=age,
        )

    lobby = Lobby(host_id=director.id, scenario_id=scenario.id, join_code=f"DEMO{secrets.token_hex(3).upper()}", visibility=Visibility.PUBLIC, status=LobbyStatus.OPEN, rules={"memory_editing": "forbidden", "interventions": ["reveal_evidence", "delay_information", "redirect_information"]})
    session.add(lobby)
    session.flush()
    cast, bindings = [], []
    for index, (key, _, _, _) in enumerate(CAST, 1):
        card = cards[key]
        session.add(LobbyMember(lobby_id=lobby.id, user_id=cast_users[key].id, role=LobbyRole.HOST if index == 1 else LobbyRole.PARTICIPANT, cast_slot=str(index), character_card_id=card.id, runtime_profile_id=runtime.id, funding_model=FundingModel.HOST, ready=True))
        cast.append({"slot": str(index), "user_id": cast_users[key].id, "character_card_id": card.id, "character_version": card.version, "name": card.name})
        bindings.append({"slot": str(index), "runtime_profile_id": runtime.id, "provider": runtime.provider, "model_id": runtime.model_id, "funding_model": FundingModel.HOST.value})

    request = SimulationRequest.model_validate({
        "seed": 1404,
        "locations": [{"id": "lounge", "name": "Safehouse Lounge"}, {"id": "station", "name": "Old Station"}, {"id": "cafe", "name": "Café Nocturne"}],
        "routes": [{"id": "lounge-station", "from_location_id": "lounge", "to_location_id": "station", "travel_minutes": 8}, {"id": "lounge-cafe", "from_location_id": "lounge", "to_location_id": "cafe", "travel_minutes": 5}, {"id": "station-cafe", "from_location_id": "station", "to_location_id": "cafe", "travel_minutes": 4}],
        "characters": [{"id": "hana", "name": "Hana", "initial_location_id": "lounge"}, {"id": "rei", "name": "Rei", "initial_location_id": "lounge"}, {"id": "mira", "name": "Mira", "initial_location_id": "cafe"}],
        "actions": [{"id": "rei-depart", "character_id": "rei", "kind": "move", "destination_id": "station", "start_at": 0}, {"id": "hana-ticket", "character_id": "hana", "kind": "observe", "content": "A torn train ticket says yesterday.", "start_at": 4}, {"id": "mira-call", "character_id": "mira", "kind": "speak", "content": "I only heard half of the call.", "start_at": 8}],
    })
    original = simulate(request)
    interventions = [{"kind": "delay_information", "reason": "The ticket delivery is delayed by an external courier.", "details": {"action_id": "hana-ticket", "minutes": 6}}]
    branched = branch(request, interventions)
    manifest = RunManifest(lobby_id=lobby.id, scenario_version=scenario.version, cast=cast, runtime_bindings=bindings, rules=lobby.rules, seed=request.seed, asset_versions={f"character:{card.id}": card.version for card in cards.values()}, intervention_rules={"allowed": lobby.rules["interventions"]})
    session.add(manifest)
    lobby.status = LobbyStatus.RUNNING
    session.commit()
    return {"case": {"title": scenario.title, "lobby_code": lobby.join_code, "manifest_id": manifest.id, "seed": request.seed}, "original": original, "branched": branched, "divergence": divergence(original, branched)}
