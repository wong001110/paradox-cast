from collections.abc import Generator
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./paradox_cast.db")
engine_options: dict = {}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
