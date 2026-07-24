"""Development-only bootstrap helpers for multi-browser local testing."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_session
from .models import (
    CharacterCard,
    RuntimeProfile,
    Scenario,
    ScenarioLocation,
    ScenarioRoute,
    User,
    Visibility,
)

router = APIRouter(prefix="/api/local", tags=["local development"])

LOCAL_USERS = [
    ("local-host", "Local Director", "Hana", 23, "warm observer"),
    ("local-rei", "Local Rei Player", "Rei", 25, "careful reasoner"),
    ("local-mira", "Local Mira Player", "Mira", 21, "playful disruptor"),
]


def _enabled() -> bool:
    configured = os.getenv("LOCAL_BOOTSTRAP_ENABLED")
    if configured is not None:
        return configured.lower() in {"1", "true", "yes"}
    return os.getenv("APP_ENV", "development").lower() != "production"


def _guard() -> None:
    if not _enabled():
        raise HTTPException(404, "local bootstrap is disabled")


def _get_or_create(session: Session, model: type, defaults: dict, **filters):
    item = session.query(model).filter_by(**filters).one_or_none()
    if item:
        return item
    item = model(**filters, **defaults)
    session.add(item)
    session.flush()
    return item


@router.post("/bootstrap")
def bootstrap(session: Session = Depends(get_session)) -> dict:
    _guard()
    users: list[dict] = []
    host: User | None = None
    for key, display_name, character_name, age, style in LOCAL_USERS:
        user = _get_or_create(
            session,
            User,
            {"display_name": display_name, "is_admin": key == "local-host"},
            id=key,
        )
        if key == "local-host":
            host = user
        runtime = _get_or_create(
            session,
            RuntimeProfile,
            {
                "provider": "mock",
                "model_id": "deterministic-v1",
                "temperature": 0.2,
                "max_tokens": 300,
                "timeout_seconds": 10,
                "retry_count": 0,
                "supports_structured_output": True,
            },
            owner_id=user.id,
            display_name=f"{character_name} Local Mock",
        )
        card = _get_or_create(
            session,
            CharacterCard,
            {
                "biography": f"{character_name} is part of the local adult default cast.",
                "profile": {"style": style},
                "visual_assets": {"reference": f"/assets/characters/{character_name.lower()}-neutral-v1.webp"},
                "visibility": Visibility.PRIVATE,
                "default_runtime_id": runtime.id,
            },
            owner_id=user.id,
            name=character_name,
            adult_age=age,
        )
        users.append(
            {
                "id": user.id,
                "display_name": user.display_name,
                "is_host": user.id == "local-host",
                "character": {"id": card.id, "name": card.name, "adult_age": card.adult_age},
                "runtime": {
                    "id": runtime.id,
                    "display_name": runtime.display_name,
                    "provider": runtime.provider,
                    "model_id": runtime.model_id,
                },
            }
        )

    assert host is not None
    scenario = _get_or_create(
        session,
        Scenario,
        {
            "synopsis": "A spring festival disappearance leaves a timeline fragment behind.",
            "world": {"tone": "everyday mystery"},
            "visibility": Visibility.PRIVATE,
        },
        owner_id=host.id,
        title="The Vanishing of April 14th",
    )
    if not session.query(ScenarioLocation).filter_by(scenario_id=scenario.id).first():
        session.add_all(
            [
                ScenarioLocation(scenario_id=scenario.id, key="lounge", name="Safehouse Lounge"),
                ScenarioLocation(scenario_id=scenario.id, key="station", name="Old Station"),
                ScenarioLocation(scenario_id=scenario.id, key="cafe", name="Café Nocturne"),
                ScenarioRoute(
                    scenario_id=scenario.id,
                    from_location_key="lounge",
                    to_location_key="station",
                    travel_seconds=480,
                    route_type="walk",
                ),
                ScenarioRoute(
                    scenario_id=scenario.id,
                    from_location_key="lounge",
                    to_location_key="cafe",
                    travel_seconds=300,
                    route_type="walk",
                ),
                ScenarioRoute(
                    scenario_id=scenario.id,
                    from_location_key="station",
                    to_location_key="cafe",
                    travel_seconds=240,
                    route_type="walk",
                ),
            ]
        )
    session.commit()
    return {
        "enabled": True,
        "users": users,
        "scenario": {
            "id": scenario.id,
            "title": scenario.title,
            "owner_id": scenario.owner_id,
            "version": scenario.version,
        },
        "instructions": "Open separate browser profiles, choose different local identities, and join the same code.",
    }


@router.get("/status")
def local_status() -> dict:
    return {"enabled": _enabled(), "app_env": os.getenv("APP_ENV", "development")}
