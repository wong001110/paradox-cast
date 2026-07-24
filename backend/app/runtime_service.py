"""Runtime adapter boundary; only the mock provider is executable in the MVP."""
from __future__ import annotations

from typing import Any


class MockRuntimeProvider:
    """Deterministic provider for tests and local timeline prototypes.

    It never calls a network provider and deliberately does not receive credentials.
    """

    name = "mock"

    def decide(
        self,
        *,
        character_id: str,
        legal_actions: list[dict[str, Any]],
        requested_action: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        legal_kinds = {str(action.get("kind")) for action in legal_actions}
        if requested_action and str(requested_action.get("kind")) in legal_kinds:
            return {"character_id": character_id, "action": requested_action, "source": "mock", "accepted": True}
        fallback = next((action for action in legal_actions if action.get("kind") == "wait"), None)
        if fallback is None:
            fallback = {"kind": "wait"}
        return {"character_id": character_id, "action": fallback, "source": "mock", "accepted": False}


def provider_for(provider: str) -> MockRuntimeProvider:
    if provider != "mock":
        raise ValueError("Only the deterministic mock provider is enabled in this build")
    return MockRuntimeProvider()
