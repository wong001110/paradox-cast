from fastapi import APIRouter

from .schemas import SimulationRequest
from .simulation import simulate

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


@router.post("/validate")
def validate(request: SimulationRequest) -> dict:
    """Pydantic validates all cross-references before returning a preview summary."""
    return {
        "valid": True,
        "locations": len(request.locations),
        "routes": len(request.routes),
        "characters": len(request.characters),
        "actions": len(request.actions),
    }


@router.post("/run")
def run(request: SimulationRequest) -> dict:
    return simulate(request)
