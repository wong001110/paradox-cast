from app.database import DATABASE_URL, engine

def test_database_configuration_uses_a_sqlite_safe_engine_locally() -> None:
    assert DATABASE_URL.startswith("sqlite")
    assert engine.url.drivername == "sqlite"
