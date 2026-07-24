"""Scenario creator endpoints and structural timeline validation."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .database import get_session
from .models import Scenario, ScenarioLocation, ScenarioRoute
from .schemas import ScenarioCreate

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def validate_blueprint(payload: ScenarioCreate) -> list[dict[str, str]]:
    """Return creator-facing validation errors without accepting an invalid graph.

    The Python simulation can only advance through explicit directed route segments;
    this validation deliberately does not infer a route from the illustration layout.
    """
    errors: list[dict[str, str]] = []
    keys = [location.key for location in payload.locations]
    known = set(keys)
    if len(keys) != len(known):
        errors.append({"field": "locations", "message": "location keys must be unique"})
    seen_routes: set[tuple[str, str]] = set()
    for route in payload.routes:
        pair = (route.from_location_key, route.to_location_key)
        if route.from_location_key not in known or route.to_location_key not in known:
            errors.append({"field": "routes", "message": f"route {pair[0]} → {pair[1]} references an unknown location"})
        if route.from_location_key == route.to_location_key:
            errors.append({"field": "routes", "message": f"route {pair[0]} cannot point to itself"})
        if pair in seen_routes:
            errors.append({"field": "routes", "message": f"duplicate directed route {pair[0]} → {pair[1]}"})
        seen_routes.add(pair)
    return errors


def location_view(location: ScenarioLocation) -> dict:
    return {"id": location.id, "key": location.key, "name": location.name, "description": location.description, "metadata": location.metadata_json}


def route_view(route: ScenarioRoute) -> dict:
    return {"id": route.id, "from_location_key": route.from_location_key, "to_location_key": route.to_location_key, "travel_seconds": route.travel_seconds, "route_type": route.route_type, "constraints": route.constraints}


def view(scenario: Scenario, session: Session) -> dict:
    locations = session.query(ScenarioLocation).filter_by(scenario_id=scenario.id).order_by(ScenarioLocation.key).all()
    routes = session.query(ScenarioRoute).filter_by(scenario_id=scenario.id).order_by(ScenarioRoute.from_location_key, ScenarioRoute.to_location_key).all()
    return {"id": scenario.id, "owner_id": scenario.owner_id, "title": scenario.title, "synopsis": scenario.synopsis, "world": scenario.world, "version": scenario.version, "visibility": scenario.visibility.value, "locations": [location_view(item) for item in locations], "routes": [route_view(item) for item in routes]}


def replace_graph(scenario: Scenario, payload: ScenarioCreate, session: Session) -> None:
    session.query(ScenarioRoute).filter_by(scenario_id=scenario.id).delete()
    session.query(ScenarioLocation).filter_by(scenario_id=scenario.id).delete()
    for location in payload.locations:
        session.add(ScenarioLocation(scenario_id=scenario.id, key=location.key, name=location.name, description=location.description, metadata_json=location.metadata))
    for route in payload.routes:
        session.add(ScenarioRoute(scenario_id=scenario.id, **route.model_dump()))


@router.post("/validate")
def validate(payload: ScenarioCreate) -> dict:
    errors = validate_blueprint(payload)
    return {"valid": not errors, "errors": errors}


@router.post("", status_code=201)
def create(payload: ScenarioCreate, owner_id: str, session: Session = Depends(get_session)) -> dict:
    errors = validate_blueprint(payload)
    if errors:
        raise HTTPException(422, {"message": "invalid scenario graph", "errors": errors})
    scenario = Scenario(owner_id=owner_id, title=payload.title, synopsis=payload.synopsis, world=payload.world, visibility=payload.visibility)
    session.add(scenario)
    session.flush()
    replace_graph(scenario, payload, session)
    session.commit()
    session.refresh(scenario)
    return view(scenario, session)


@router.get("")
def list_scenarios(owner_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [view(scenario, session) for scenario in session.query(Scenario).filter_by(owner_id=owner_id).order_by(Scenario.title).all()]


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str, session: Session = Depends(get_session)) -> dict:
    scenario = session.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(404, "scenario not found")
    return view(scenario, session)


@router.put("/{scenario_id}")
def update(scenario_id: str, payload: ScenarioCreate, owner_id: str, session: Session = Depends(get_session)) -> dict:
    scenario = session.get(Scenario, scenario_id)
    if not scenario or scenario.owner_id != owner_id:
        raise HTTPException(404, "scenario not found")
    errors = validate_blueprint(payload)
    if errors:
        raise HTTPException(422, {"message": "invalid scenario graph", "errors": errors})
    scenario.title, scenario.synopsis, scenario.world, scenario.visibility = payload.title, payload.synopsis, payload.world, payload.visibility
    scenario.version += 1
    replace_graph(scenario, payload, session)
    session.commit()
    return view(scenario, session)


@router.delete("/{scenario_id}", status_code=204)
def delete(scenario_id: str, owner_id: str, session: Session = Depends(get_session)) -> Response:
    scenario = session.get(Scenario, scenario_id)
    if not scenario or scenario.owner_id != owner_id:
        raise HTTPException(404, "scenario not found")
    session.query(ScenarioRoute).filter_by(scenario_id=scenario.id).delete()
    session.query(ScenarioLocation).filter_by(scenario_id=scenario.id).delete()
    session.delete(scenario)
    session.commit()
    return Response(status_code=204)
