from fastapi import APIRouter, HTTPException
from .branching import branch, divergence
from .schemas import SimulationRequest
from .simulation import simulate
router=APIRouter(prefix="/api/branches",tags=["branches"])
@router.post("/replay")
def replay(request: SimulationRequest, interventions: list[dict]) -> dict:
    original=simulate(request)
    try: branched=branch(request,interventions)
    except ValueError as error: raise HTTPException(422,str(error))
    return {"original":original,"branched":branched,"divergence":divergence(original,branched)}
