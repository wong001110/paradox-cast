from app.schemas import SimulationRequest
from app.simulation import simulate


def test_kernel_resolves_route_travel_crossing_and_information_events_deterministically() -> None:
    request = SimulationRequest.model_validate({
        "seed": 42,
        "locations": [{"id": "lounge", "name": "Lounge"}, {"id": "station", "name": "Station"}],
        "routes": [{"id": "walkway", "from_location_id": "lounge", "to_location_id": "station", "travel_minutes": 10}],
        "characters": [
            {"id": "hana", "name": "Hana", "initial_location_id": "lounge"},
            {"id": "rei", "name": "Rei", "initial_location_id": "station"},
            {"id": "mira", "name": "Mira", "initial_location_id": "lounge"},
            {"id": "kagura", "name": "Kagura", "initial_location_id": "lounge"},
        ],
        "actions": [
            {"id": "h-move", "character_id": "hana", "kind": "move", "destination_id": "station"},
            {"id": "r-move", "character_id": "rei", "kind": "move", "destination_id": "lounge"},
            {"id": "m-observe", "character_id": "mira", "kind": "observe", "start_at": 1, "content": "a torn ticket"},
            {"id": "m-talk", "character_id": "mira", "kind": "speak", "start_at": 2, "content": "The train ticket says yesterday."},
            {"id": "m-intercept", "character_id": "mira", "kind": "intercept", "target_character_id": "rei", "start_at": 15, "content": "Wait."},
        ],
    })

    first, second = simulate(request), simulate(request)
    assert first == second
    types = [event["type"] for event in first["events"]]
    assert "route_segment_traversed" in types
    assert "crossed_path_encounter" in types
    assert "observation" in types
    assert "partial_overhearing" in types
    assert "interception" in types
    assert first["final_state"]["hana"] == {"location_id": "station", "available_at": 10}


def test_kernel_rejects_unreachable_destination_instead_of_mutating_state() -> None:
    request = SimulationRequest.model_validate({
        "locations": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
        "characters": [{"id": "hana", "name": "Hana", "initial_location_id": "a"}],
        "actions": [{"character_id": "hana", "kind": "move", "destination_id": "b"}],
    })
    result = simulate(request)
    assert result["events"][0]["type"] == "action_rejected"
    assert result["events"][0]["details"]["reason"] == "no_legal_route"
    assert result["final_state"]["hana"]["location_id"] == "a"
