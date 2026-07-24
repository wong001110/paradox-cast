import pytest
from fastapi.testclient import TestClient
from app.branching import branch, divergence
from app.main import app
from app.schemas import SimulationRequest
def test_branch_rejects_memory_surgery_and_replays_external_change() -> None:
    payload={"seed":1,"locations":[{"id":"a","name":"A"},{"id":"b","name":"B"}],"routes":[{"id":"r","from_location_id":"a","to_location_id":"b","travel_minutes":5}],"characters":[{"id":"hana","name":"Hana","initial_location_id":"a"}],"actions":[{"id":"go","character_id":"hana","kind":"move","destination_id":"b","start_at":0}]}
    original=branch(SimulationRequest.model_validate(payload),[])
    replay=branch(SimulationRequest.model_validate(payload),[{"kind":"delay_information","details":{"action_id":"go","minutes":4}}])
    assert divergence(original,replay)["final_state_changed"] is True
    with pytest.raises(ValueError,match="not allowed"):
        branch(SimulationRequest.model_validate(payload),[{"kind":"implant_memory"}])

    response = TestClient(app).post("/api/branches/replay", json={"simulation": payload, "interventions": [{"kind": "delay_information", "details": {"action_id": "go", "minutes": 2}}]})
    assert response.status_code == 200
    assert response.json()["branched"]["interventions"][0]["kind"] == "delay_information"
