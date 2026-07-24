from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.main import app
from app.models import Credential, User


def _owner() -> str:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(display_name="Runtime owner")
        session.add(user)
        session.commit()
        return user.id


def test_credential_is_masked_and_runtime_mock_never_returns_secret() -> None:
    owner_id = _owner()
    client = TestClient(app)
    secret = "pc-secret-1234"

    credential = client.post(
        f"/api/credentials?owner_id={owner_id}",
        json={"provider": "mock", "label": "Local test", "api_secret": secret},
    )
    assert credential.status_code == 201
    view = credential.json()
    assert view["masked_identifier"] == "••••1234"
    assert secret not in str(view)
    with Session(engine) as session:
        stored = session.get(Credential, view["id"])
        assert stored is not None and stored.secret_ciphertext != secret

    runtime = client.post(
        f"/api/runtimes?owner_id={owner_id}",
        json={"display_name": "Mock", "provider": "mock", "model_id": "mock-v1", "credential_id": view["id"]},
    )
    assert runtime.status_code == 201
    decision = client.post(
        f"/api/runtimes/{runtime.json()['id']}/decide?owner_id={owner_id}",
        json={"character_id": "hana", "legal_actions": [{"kind": "wait"}, {"kind": "observe"}], "requested_action": {"kind": "observe"}},
    )
    assert decision.status_code == 200
    assert decision.json()["action"] == {"kind": "observe"}
    assert secret not in str(decision.json())


def test_runtime_requires_credential_owned_by_same_user() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner_one, owner_two = User(display_name="One"), User(display_name="Two")
        session.add_all([owner_one, owner_two])
        session.commit()
        first, second = owner_one.id, owner_two.id
    client = TestClient(app)
    credential = client.post(
        f"/api/credentials?owner_id={first}",
        json={"provider": "mock", "label": "One", "api_secret": "secret"},
    ).json()
    response = client.post(
        f"/api/runtimes?owner_id={second}",
        json={"display_name": "Bad bind", "provider": "mock", "model_id": "mock-v1", "credential_id": credential["id"]},
    )
    assert response.status_code == 422
