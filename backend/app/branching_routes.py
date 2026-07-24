from fastapi import APIRouter, HTTPException
from .branching import branch, divergence
from .schemas import BranchReplayRequest
from .simulation import simulate
router=APIRouter(prefix="/api/branches",tags=["branches"])
@router.post("/replay")
def replay(payload: BranchReplayRequest) -> dict:
    original=simulate(payload.simulation)
    try: branched=branch(payload.simulation,payload.interventions)
    except ValueError as error: raise HTTPException(422,str(error))
    return {"original":original,"branched":branched,"divergence":divergence(original,branched)}
