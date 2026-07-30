"""End-to-end AI run orchestration for a frozen Paradox Cast manifest.

Runtime providers choose one server-supplied legal action per character and turn.
The deterministic simulation kernel remains authoritative for legality, travel,
encounters, ordered events, replay, and explainable branches.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from .branching import branch, divergence
from .credential_service import decrypt_secret
from .models import (
    CharacterCard,
    Credential,
    Lobby,
    RunManifest,
    RuntimeProfile,
    Scenario,
    ScenarioLocation,
    ScenarioRoute,
)
from .runtime_service import RuntimeProviderError, provider_for
from .schemas import SimulationRequest
from .simulation import simulate


class AIRunConfigurationError(ValueError):
    """Raised when a frozen manifest cannot be executed safely."""


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "character"


def _slot_key(value: object) -> tuple[int, str]:
    text = str(value or "")
    return (int(text), text) if text.isdigit() else (10_000, text)


def _runtime_provider(session: Session, profile: RuntimeProfile):
    secret: str | None = None
    if profile.credential_id:
        credential = session.get(Credential, profile.credential_id)
        if not credential or credential.owner_id != profile.owner_id:
            raise AIRunConfigurationError("a runtime credential is unavailable")
        try:
            secret = decrypt_secret(credential.secret_ciphertext)
        except Exception as error:
            raise AIRunConfigurationError(
                "a runtime credential cannot be decrypted; configure a stable PARADOX_CAST_CREDENTIAL_KEY"
            ) from error
    return provider_for(profile, secret)


def _initial_location(
    scenario: Scenario,
    card: CharacterCard,
    slot: str,
    index: int,
    location_ids: list[str],
) -> str:
    configured = scenario.world.get("initial_locations", {}) if isinstance(scenario.world, dict) else {}
    if isinstance(configured, dict):
        for key in (card.id, card.name, _slug(card.name), slot):
            location_id = configured.get(key)
            if isinstance(location_id, str) and location_id in location_ids:
                return location_id
    return location_ids[index % len(location_ids)]


def _evidence_text(scenario: Scenario, location_id: str, turn: int) -> str:
    world = scenario.world if isinstance(scenario.world, dict) else {}
    evidence = world.get("evidence", [])
    if isinstance(evidence, list) and evidence:
        item = evidence[turn % len(evidence)]
        if isinstance(item, str) and item.strip():
            return item.strip()[:500]
        if isinstance(item, dict):
            content = item.get("content") or item.get("description") or item.get("title")
            if isinstance(content, str) and content.strip():
                return content.strip()[:500]
    return f"A clue at {location_id} may explain part of {scenario.title}."


def _legal_actions(
    *,
    scenario: Scenario,
    character_name: str,
    character_id: str,
    location_id: str,
    turn: int,
    neighbors: dict[str, set[str]],
    planned_locations: dict[str, str],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {"kind": "wait"},
        {"kind": "observe", "content": _evidence_text(scenario, location_id, turn)},
    ]
    for destination_id in sorted(neighbors.get(location_id, set())):
        actions.append({"kind": "move", "destination_id": destination_id})

    co_located = sorted(
        other_id
        for other_id, other_location in planned_locations.items()
        if other_id != character_id and other_location == location_id
    )
    if co_located:
        actions.append(
            {
                "kind": "speak",
                "target_character_id": co_located[0],
                "content": f"{character_name} shares a current suspicion about {scenario.title}.",
            }
        )
    return actions


def _annotate_events(result: dict, decisions: list[dict]) -> dict:
    by_action_id = {decision["action_id"]: decision for decision in decisions}
    for event in result.get("events", []):
        details = event.get("details")
        if not isinstance(details, dict):
            continue
        action_id = details.get("action_id")
        decision = by_action_id.get(action_id)
        if not decision:
            continue
        domain_source = details.get("source")
        if domain_source and domain_source != decision["source"]:
            details.setdefault("simulation_source", domain_source)
        details["source"] = decision["source"]
        details.setdefault("model_id", decision["model_id"])
        details.setdefault("runtime_profile_id", decision["runtime_profile_id"])
        details.setdefault("decision_reason", decision["reason"])
    return result


def run_manifest_with_ai(
    session: Session,
    manifest: RunManifest,
    *,
    turns: int = 2,
    allow_fallback: bool = True,
) -> dict:
    if turns < 1 or turns > 4:
        raise AIRunConfigurationError("turns must be between 1 and 4")

    lobby = session.get(Lobby, manifest.lobby_id)
    if not lobby:
        raise AIRunConfigurationError("the manifest lobby no longer exists")
    scenario = session.get(Scenario, lobby.scenario_id)
    if not scenario:
        raise AIRunConfigurationError("the manifest scenario no longer exists")

    locations = (
        session.query(ScenarioLocation)
        .filter_by(scenario_id=scenario.id)
        .order_by(ScenarioLocation.key)
        .all()
    )
    routes = (
        session.query(ScenarioRoute)
        .filter_by(scenario_id=scenario.id)
        .order_by(ScenarioRoute.from_location_key, ScenarioRoute.to_location_key)
        .all()
    )
    if not locations:
        raise AIRunConfigurationError("the scenario has no locations")

    location_ids = [location.key for location in locations]
    location_set = set(location_ids)
    neighbors: dict[str, set[str]] = defaultdict(set)
    route_payload: list[dict[str, Any]] = []
    for route in routes:
        if route.from_location_key not in location_set or route.to_location_key not in location_set:
            raise AIRunConfigurationError("a scenario route references an unknown location")
        travel_minutes = max(1, round(route.travel_seconds / 60))
        route_payload.append(
            {
                "id": route.id,
                "from_location_id": route.from_location_key,
                "to_location_id": route.to_location_key,
                "travel_minutes": travel_minutes,
                "bidirectional": True,
            }
        )
        neighbors[route.from_location_key].add(route.to_location_key)
        neighbors[route.to_location_key].add(route.from_location_key)

    binding_by_slot = {str(item.get("slot")): item for item in manifest.runtime_bindings}
    cast_entries = sorted(manifest.cast, key=lambda item: _slot_key(item.get("slot")))
    if not cast_entries:
        raise AIRunConfigurationError("the manifest has no cast")

    characters: list[dict[str, Any]] = []
    cast_runtime: list[tuple[str, str, CharacterCard, RuntimeProfile]] = []
    planned_locations: dict[str, str] = {}
    used_character_ids: set[str] = set()

    for index, cast_entry in enumerate(cast_entries):
        slot = str(cast_entry.get("slot") or index + 1)
        card_id = cast_entry.get("character_card_id")
        binding = binding_by_slot.get(slot)
        if not isinstance(card_id, str) or not binding:
            raise AIRunConfigurationError("the manifest contains an incomplete cast/runtime binding")
        runtime_id = binding.get("runtime_profile_id")
        card = session.get(CharacterCard, card_id)
        runtime = session.get(RuntimeProfile, runtime_id) if isinstance(runtime_id, str) else None
        if not card or not runtime:
            raise AIRunConfigurationError("a frozen character or runtime no longer exists")

        base_id = _slug(card.name)
        character_id = base_id
        suffix = 2
        while character_id in used_character_ids:
            character_id = f"{base_id}-{suffix}"
            suffix += 1
        used_character_ids.add(character_id)
        initial_location_id = _initial_location(scenario, card, slot, index, location_ids)
        planned_locations[character_id] = initial_location_id
        characters.append(
            {"id": character_id, "name": card.name, "initial_location_id": initial_location_id}
        )
        cast_runtime.append((slot, character_id, card, runtime))

    actions: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for turn in range(turns):
        for actor_index, (slot, character_id, card, runtime) in enumerate(cast_runtime):
            location_id = planned_locations[character_id]
            legal_actions = _legal_actions(
                scenario=scenario,
                character_name=card.name,
                character_id=character_id,
                location_id=location_id,
                turn=turn,
                neighbors=neighbors,
                planned_locations=planned_locations,
            )
            context = {
                "scenario": {
                    "title": scenario.title,
                    "synopsis": scenario.synopsis,
                    "world": scenario.world,
                },
                "character": {
                    "name": card.name,
                    "biography": card.biography,
                    "profile": card.profile,
                },
                "turn": turn + 1,
                "location_id": location_id,
                "other_character_locations": {
                    other_id: other_location
                    for other_id, other_location in planned_locations.items()
                    if other_id != character_id
                },
                "previous_decisions": [
                    {
                        "character_id": item["character_id"],
                        "action": item["action"],
                        "reason": item["reason"],
                    }
                    for item in decisions[-6:]
                ],
                "rules": manifest.rules,
            }
            requested_action = None
            if runtime.provider == "mock":
                requested_action = legal_actions[(turn + actor_index + 1) % len(legal_actions)]

            try:
                provider = _runtime_provider(session, runtime)
                decision = provider.decide(
                    character_id=character_id,
                    legal_actions=legal_actions,
                    requested_action=requested_action,
                    context=context,
                )
            except (AIRunConfigurationError, RuntimeProviderError) as error:
                if not allow_fallback:
                    raise
                decision = {
                    "character_id": character_id,
                    "action": {"kind": "wait"},
                    "source": "fallback",
                    "accepted": False,
                    "model_id": runtime.model_id,
                    "reason": "The configured runtime failed, so the server selected a legal wait action.",
                }
                failures.append(
                    {
                        "character_id": character_id,
                        "runtime_profile_id": runtime.id,
                        "provider": runtime.provider,
                        "error": str(error),
                    }
                )

            selected = decision.get("action")
            if not isinstance(selected, dict) or selected not in legal_actions:
                if not allow_fallback:
                    raise RuntimeProviderError("the runtime selected an action outside the legal set")
                selected = {"kind": "wait"}
                decision = {
                    **decision,
                    "action": selected,
                    "source": "fallback",
                    "accepted": False,
                    "reason": "The runtime returned an invalid action, so the server selected wait.",
                }
                failures.append(
                    {
                        "character_id": character_id,
                        "runtime_profile_id": runtime.id,
                        "provider": runtime.provider,
                        "error": "runtime selected an action outside the legal set",
                    }
                )

            action_id = f"ai-t{turn + 1}-{character_id}"
            action = {
                **selected,
                "id": action_id,
                "character_id": character_id,
                "start_at": turn * 12 + actor_index * 2,
            }
            actions.append(action)
            if action.get("kind") in {"move", "change_destination"} and isinstance(
                action.get("destination_id"), str
            ):
                planned_locations[character_id] = action["destination_id"]

            decisions.append(
                {
                    "action_id": action_id,
                    "turn": turn + 1,
                    "slot": slot,
                    "character_id": character_id,
                    "character_name": card.name,
                    "runtime_profile_id": runtime.id,
                    "provider": runtime.provider,
                    "source": str(decision.get("source") or runtime.provider),
                    "model_id": str(decision.get("model_id") or runtime.model_id),
                    "accepted": bool(decision.get("accepted", True)),
                    "reason": str(decision.get("reason") or "Runtime selected a legal action."),
                    "action": selected,
                    "usage": decision.get("usage"),
                }
            )

    request = SimulationRequest.model_validate(
        {
            "seed": manifest.seed,
            "locations": [{"id": location.key, "name": location.name} for location in locations],
            "routes": route_payload,
            "characters": characters,
            "actions": actions,
        }
    )
    original = _annotate_events(simulate(request), decisions)

    branch_action = next(
        (action for action in actions if action.get("kind") in {"observe", "speak", "intercept"}),
        actions[0],
    )
    interventions = [
        {
            "kind": "delay_information",
            "reason": "An external delivery delay shifts one AI-selected action by four minutes.",
            "details": {"action_id": branch_action["id"], "minutes": 4},
        }
    ]
    branched = _annotate_events(branch(request, interventions), decisions)

    provider_summary = [
        {
            "runtime_profile_id": runtime.id,
            "display_name": runtime.display_name,
            "provider": runtime.provider,
            "model_id": runtime.model_id,
        }
        for runtime in {item[3].id: item[3] for item in cast_runtime}.values()
    ]
    return {
        "case": {
            "title": scenario.title,
            "lobby_code": lobby.join_code,
            "manifest_id": manifest.id,
            "seed": manifest.seed,
            "mode": "ai",
            "turns": turns,
            "provider_summary": provider_summary,
            "fallback_used": bool(failures),
        },
        "original": original,
        "branched": branched,
        "divergence": divergence(original, branched),
        "decisions": decisions,
        "runtime_failures": failures,
    }
