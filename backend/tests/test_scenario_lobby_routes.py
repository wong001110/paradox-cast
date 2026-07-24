from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.main import app
from app.models import CharacterCard, RuntimeProfile, User


def reset_users() -> tuple[str, str]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        host, guest = User(display_name="Director"), User(display_name="Guest")
        session.add_all([host, guest])
        session.commit()
        return host.id, guest.id


def create_scenario(client: TestClient, owner_id: str) -> dict:
    response = client.post(
        f"/api/scenarios?owner_id={owner_id}",
        json={
            "title": "The Vanishing of April 14th",
            "synopsis": "A closed-room timeline mystery.",
            "world": {"goals": ["expose the truth"], "rules": {"max_turns": 12}},
            "locations": [
                {"key": "lounge", "name": "Safehouse Lounge"},
                {"key": "station", "name": "Old Station"},
            ],
            "routes": [{"from_location_key": "lounge", "to_location_key": "station", "travel_seconds": 90}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_scenario_crud_validates_explicit_route_graph() -> None:
    host_id, _ = reset_users()
    client = TestClient(app)
    invalid = client.post(
        "/api/scenarios/validate",
        json={
            "title": "Broken", "locations": [{"key": "lounge", "name": "Lounge"}],
            "routes": [{"from_location_key": "lounge", "to_location_key": "missing", "travel_seconds": 5}],
        },
    )
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False

    scenario = create_scenario(client, host_id)
    assert scenario["locations"][0]["key"] == "lounge"
    assert scenario["routes"][0]["travel_seconds"] == 90
    updated = client.put(
        f"/api/scenarios/{scenario['id']}?owner_id={host_id}",
        json={
            "title": "The Vanishing of April 14th (Revised)",
            "locations": [{"key": "lounge", "name": "Safehouse Lounge"}],
            "routes": [],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["routes"] == []


def test_lobby_ready_check_and_manifest_freeze() -> None:
    host_id, guest_id = reset_users()
    client = TestClient(app)
    scenario = create_scenario(client, host_id)
    with Session(engine) as session:
        host_card = CharacterCard(owner_id=host_id, name="Hana", adult_age=22)
        guest_card = CharacterCard(owner_id=guest_id, name="Rei", adult_age=24)
        host_runtime = RuntimeProfile(owner_id=host_id, display_name="Host mock", provider="mock", model_id="mock-v1")
        guest_runtime = RuntimeProfile(owner_id=guest_id, display_name="Guest mock", provider="mock", model_id="mock-v1")
        session.add_all([host_card, guest_card, host_runtime, guest_runtime])
        session.commit()
        ids = host_card.id, guest_card.id, host_runtime.id, guest_runtime.id

    lobby_response = client.post(
        f"/api/lobbies?owner_id={host_id}",
        json={"scenario_id": scenario["id"], "visibility": "public", "rules": {"allow_interventions": True}},
    )
    assert lobby_response.status_code == 201, lobby_response.text
    lobby = lobby_response.json()
    assert client.get("/api/lobbies").json()[0]["id"] == lobby["id"]
    joined = client.post("/api/lobbies/join", params={"user_id": guest_id}, json={"join_code": lobby["join_code"]})
    assert joined.status_code == 200, joined.text

    for user_id, slot, card_id, runtime_id in ((host_id, "lead", ids[0], ids[2]), (guest_id, "observer", ids[1], ids[3])):
        binding = client.put(f"/api/lobbies/{lobby['id']}/binding?user_id={user_id}", json={"cast_slot": slot, "character_card_id": card_id, "runtime_profile_id": runtime_id})
        assert binding.status_code == 200, binding.text
        ready = client.put(f"/api/lobbies/{lobby['id']}/ready?user_id={user_id}", json={"ready": True})
        assert ready.status_code == 200, ready.text

    started = client.post(f"/api/lobbies/{lobby['id']}/start?owner_id={host_id}", json={"seed": 42, "intervention_rules": {"allowed": ["reveal_evidence"]}})
    assert started.status_code == 201, started.text
    manifest = started.json()
    assert manifest["seed"] == 42
    assert len(manifest["cast"]) == 2
    assert manifest["runtime_bindings"][0]["model_id"] == "mock-v1"
    assert client.get(f"/api/lobbies/{lobby['id']}").json()["status"] == "running"


def test_lobby_requires_complete_binding_before_ready() -> None:
    host_id, _ = reset_users()
    client = TestClient(app)
    scenario = create_scenario(client, host_id)
    lobby = client.post(f"/api/lobbies?owner_id={host_id}", json={"scenario_id": scenario["id"]}).json()
    response = client.put(f"/api/lobbies/{lobby['id']}/ready?user_id={host_id}", json={"ready": True})
    assert response.status_code == 422
