from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app

def test_demo_run_persists_manifest_and_returns_real_divergence() -> None:
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    response = TestClient(app).post("/api/demo/run")
    assert response.status_code == 200
    payload = response.json()
    assert payload["case"]["manifest_id"]
    assert payload["original"]["events"]
    assert payload["branched"]["interventions"][0]["kind"] == "delay_information"
