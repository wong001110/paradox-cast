from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app
from app.models import User
from sqlalchemy.orm import Session

def owner() -> str:
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with Session(engine) as s: u=User(display_name="Owner"); s.add(u); s.commit(); return u.id

def test_character_fork_and_export_exclude_runtime_secrets() -> None:
    user_id=owner(); client=TestClient(app)
    created=client.post(f"/api/characters?owner_id={user_id}",json={"name":"Hana","adult_age":21,"profile":{"values":["care"]},"visibility":"unlisted"}).json()
    exported=client.get(f"/api/characters/{created['id']}/export").json()
    assert "api_secret" not in str(exported)
    fork=client.post(f"/api/characters/{created['id']}/duplicate?owner_id={user_id}").json()
    assert fork["forked_from_id"] == created["id"] and fork["visibility"] == "private"
