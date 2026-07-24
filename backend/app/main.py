from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 - registers SQLAlchemy metadata
from .asset_routes import router as asset_router
from .branching_routes import router as branching_router
from .character_routes import router as character_router
from .database import Base, engine
from .demo_routes import router as demo_router
from .lobby_routes import router as lobby_router
from .lobby_socket_routes import router as lobby_socket_router
from .local_routes import router as local_router
from .runtime_routes import router as runtime_router
from .scenario_routes import router as scenario_router
from .simulation_routes import router as simulation_router
from .system_routes import router as system_router

app = FastAPI(
    title="Paradox Cast API",
    version="0.2.0",
    description="The authoritative timeline simulation API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.getenv("AUTO_CREATE_SCHEMA", "true").lower() in {"1", "true", "yes"}:
    Base.metadata.create_all(bind=engine)

app.include_router(character_router)
app.include_router(scenario_router)
app.include_router(lobby_router)
app.include_router(lobby_socket_router)
app.include_router(runtime_router)
app.include_router(asset_router)
app.include_router(system_router)
app.include_router(local_router)
app.include_router(simulation_router)
app.include_router(branching_router)
app.include_router(demo_router)


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "paradox-cast-api"}
