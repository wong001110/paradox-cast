from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from . import models
from .character_routes import router as character_router
from .lobby_routes import router as lobby_router
from .scenario_routes import router as scenario_router
from .runtime_routes import router as runtime_router
from .simulation_routes import router as simulation_router
from .branching_routes import router as branching_router

app = FastAPI(
    title="Paradox Cast API",
    version="0.1.0",
    description="The authoritative timeline simulation API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
Base.metadata.create_all(bind=engine)
app.include_router(character_router)
app.include_router(scenario_router)
app.include_router(lobby_router)
app.include_router(runtime_router)
app.include_router(simulation_router)
app.include_router(branching_router)


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "paradox-cast-api"}
