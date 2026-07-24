"""Explainable MVP branching: only external interventions alter a replay request."""
from copy import deepcopy
from .schemas import SimulationRequest
from .simulation import simulate

ALLOWED_INTERVENTIONS = {"reveal_evidence", "redirect_information", "delay_information", "change_starting_condition", "change_item_state", "swap_runtime"}

def branch(request: SimulationRequest, interventions: list[dict]) -> dict:
    changed = request.model_dump()
    audit=[]
    for intervention in interventions:
        kind=intervention.get("kind")
        if kind not in ALLOWED_INTERVENTIONS: raise ValueError(f"intervention not allowed: {kind}")
        audit.append({"kind":kind,"reason":intervention.get("reason","external intervention"),"details":intervention.get("details",{})})
        if kind == "change_starting_condition":
            character_id=intervention.get("details",{}).get("character_id"); location=intervention.get("details",{}).get("initial_location_id")
            for character in changed["characters"]:
                if character["id"] == character_id and location: character["initial_location_id"]=location
        if kind == "delay_information":
            action_id=intervention.get("details",{}).get("action_id"); minutes=int(intervention.get("details",{}).get("minutes",0))
            for action in changed["actions"]:
                if action.get("id") == action_id: action["start_at"] += max(0,minutes)
    result=simulate(SimulationRequest.model_validate(changed))
    result["interventions"]=audit
    return result

def divergence(original: dict, branched: dict) -> dict:
    original_events={(e["type"],e["at"],str(e["details"])) for e in original["events"]}
    branch_events={(e["type"],e["at"],str(e["details"])) for e in branched["events"]}
    return {"added_events":len(branch_events-original_events),"removed_events":len(original_events-branch_events),"final_state_changed":original["final_state"] != branched["final_state"]}
