"""Deterministic, replayable timeline simulation kernel.

LLMs may propose high-level actions, but this module is the sole authority for
route legality, travel time, encounters, observation, overhearing, interception,
and the resulting ordered event log. It has no database or network dependency.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .schemas import RouteSegment, SimulationAction, SimulationRequest


@dataclass(frozen=True)
class _Route:
    source: str
    destination: str
    travel_minutes: int
    route_id: str


@dataclass
class _State:
    location_id: str
    available_at: int = 0


@dataclass(frozen=True)
class _Transit:
    character_id: str
    source: str
    destination: str
    started_at: int
    arrived_at: int
    route_id: str


def _event(kind: str, at: int, **details: object) -> dict:
    return {"type": kind, "at": at, "details": details}


class SimulationKernel:
    def __init__(self, request: SimulationRequest):
        self.request = request
        self.events: list[dict] = []
        self.states = {item.id: _State(item.initial_location_id) for item in request.characters}
        self._names = {item.id: item.name for item in request.characters}
        self._routes = self._build_routes(request.routes)
        self._transits: list[_Transit] = []

    @staticmethod
    def _build_routes(routes: Iterable[RouteSegment]) -> dict[str, list[_Route]]:
        graph: dict[str, list[_Route]] = defaultdict(list)
        for index, route in enumerate(routes):
            route_id = route.id or f"route-{index + 1}"
            graph[route.from_location_id].append(_Route(route.from_location_id, route.to_location_id, route.travel_minutes, route_id))
            if route.bidirectional:
                graph[route.to_location_id].append(_Route(route.to_location_id, route.from_location_id, route.travel_minutes, route_id))
        return graph

    def _shortest_path(self, source: str, destination: str) -> list[_Route] | None:
        if source == destination:
            return []
        # Tie-break by route id / node id so a route selection is stable across runs.
        queue: list[tuple[int, str, tuple[str, ...], list[_Route]]] = [(0, source, (), [])]
        best: dict[str, tuple[int, tuple[str, ...]]] = {source: (0, ())}
        while queue:
            cost, node, key, path = heapq.heappop(queue)
            if best.get(node) != (cost, key):
                continue
            if node == destination:
                return path
            for edge in sorted(self._routes.get(node, []), key=lambda item: (item.route_id, item.destination)):
                next_cost, next_key = cost + edge.travel_minutes, key + (f"{edge.route_id}:{edge.destination}",)
                if edge.destination not in best or (next_cost, next_key) < best[edge.destination]:
                    best[edge.destination] = (next_cost, next_key)
                    heapq.heappush(queue, (next_cost, edge.destination, next_key, path + [edge]))
        return None

    def _reject(self, action: SimulationAction, at: int, reason: str) -> None:
        self.events.append(_event("action_rejected", at, action_id=action.id, character_id=action.character_id, action=action.kind, reason=reason))

    def _move(self, action: SimulationAction) -> None:
        if not action.destination_id:
            self._reject(action, action.start_at, "destination_required")
            return
        state = self.states[action.character_id]
        started_at = max(action.start_at, state.available_at)
        path = self._shortest_path(state.location_id, action.destination_id)
        if path is None:
            self._reject(action, started_at, "no_legal_route")
            return
        if not path:
            self.events.append(_event("destination_unchanged", started_at, action_id=action.id, character_id=action.character_id, location_id=state.location_id))
            return
        self.events.append(_event("movement_started", started_at, character_id=action.character_id, from_location_id=state.location_id, destination_id=action.destination_id, action_id=action.id))
        cursor = started_at
        for edge in path:
            arrival = cursor + edge.travel_minutes
            self._transits.append(_Transit(action.character_id, edge.source, edge.destination, cursor, arrival, edge.route_id))
            self.events.append(_event("route_segment_traversed", cursor, action_id=action.id, character_id=action.character_id, route_id=edge.route_id, from_location_id=edge.source, to_location_id=edge.destination, arrived_at=arrival))
            cursor = arrival
        state.location_id, state.available_at = action.destination_id, cursor
        self.events.append(_event("movement_arrived", cursor, character_id=action.character_id, location_id=action.destination_id, action_id=action.id))

    def _at_location(self, action: SimulationAction) -> tuple[_State, int]:
        state = self.states[action.character_id]
        return state, max(action.start_at, state.available_at)

    def _observe(self, action: SimulationAction) -> None:
        state, at = self._at_location(action)
        self.events.append(_event("observation", at, action_id=action.id, character_id=action.character_id, location_id=state.location_id, target_character_id=action.target_character_id, content=action.content, source="direct_observation"))

    def _speak(self, action: SimulationAction) -> None:
        state, at = self._at_location(action)
        recipients = [
            character_id for character_id, other in self.states.items()
            if character_id != action.character_id and other.location_id == state.location_id and other.available_at <= at
        ]
        self.events.append(_event("dialogue", at, action_id=action.id, speaker_id=action.character_id, location_id=state.location_id, target_character_id=action.target_character_id, content=action.content, recipients=recipients))
        # Hearing is a separate event so the replay can explain information sources.
        for listener_id in recipients:
            if listener_id == action.target_character_id:
                continue
            partial = action.content[: max(1, len(action.content) // 2)] if action.content else ""
            self.events.append(_event("partial_overhearing", at, action_id=action.id, character_id=listener_id, speaker_id=action.character_id, location_id=state.location_id, content=partial, source="overheard", confidence=0.5))

    def _intercept(self, action: SimulationAction) -> None:
        state, at = self._at_location(action)
        target = self.states.get(action.target_character_id or "")
        if not target or target.location_id != state.location_id or target.available_at > at:
            self._reject(action, at, "target_not_interceptable")
            return
        self.events.append(_event("interception", at, action_id=action.id, character_id=action.character_id, target_character_id=action.target_character_id, location_id=state.location_id, content=action.content, source="direct_interception"))

    def _execute(self, action: SimulationAction) -> None:
        if action.kind in {"move", "change_destination"}:
            self._move(action)
        elif action.kind == "observe":
            self._observe(action)
        elif action.kind == "speak":
            self._speak(action)
        elif action.kind == "intercept":
            self._intercept(action)
        else:
            state, at = self._at_location(action)
            self.events.append(_event("wait", at, character_id=action.character_id, location_id=state.location_id, action_id=action.id))

    def _add_encounters(self) -> None:
        # Intersecting route segments cause a crossed-path encounter when intervals overlap.
        seen: set[tuple[str, str, str, int]] = set()
        for left, right in combinations(self._transits, 2):
            if left.character_id == right.character_id or left.route_id != right.route_id:
                continue
            if left.source != right.destination or left.destination != right.source:
                continue
            overlap_start, overlap_end = max(left.started_at, right.started_at), min(left.arrived_at, right.arrived_at)
            if overlap_start >= overlap_end:
                continue
            pair = tuple(sorted((left.character_id, right.character_id)))
            key = (pair[0], pair[1], left.route_id, overlap_start)
            if key not in seen:
                seen.add(key)
                self.events.append(_event("crossed_path_encounter", overlap_start, character_ids=list(pair), route_id=left.route_id, from_location_id=left.source, to_location_id=left.destination, overlap_until=overlap_end))

        # Arrival encounters are a convenience presentation event; the state transition
        # remains represented independently by movement_arrived.
        arrival_events = [event for event in self.events if event["type"] == "movement_arrived"]
        for event in arrival_events:
            details = event["details"]
            arriving_id, at, location_id = details["character_id"], event["at"], details["location_id"]
            co_located = [character_id for character_id, state in self.states.items() if character_id != arriving_id and state.location_id == location_id and state.available_at <= at]
            for other_id in sorted(co_located):
                self.events.append(_event("location_encounter", at, character_ids=sorted([arriving_id, other_id]), location_id=location_id))

    def run(self) -> dict:
        for action in sorted(enumerate(self.request.actions), key=lambda item: (item[1].start_at, item[0])):
            self._execute(action[1])
        self._add_encounters()
        # Stable ordering makes a run replayable and suitable for a snapshot hash later.
        self.events.sort(key=lambda item: (item["at"], item["type"], str(item["details"])))
        return {
            "seed": self.request.seed,
            "events": self.events,
            "final_state": {
                character_id: {"location_id": state.location_id, "available_at": state.available_at}
                for character_id, state in sorted(self.states.items())
            },
        }


def simulate(request: SimulationRequest) -> dict:
    return SimulationKernel(request).run()
