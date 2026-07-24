"""AI runtime adapters.

The simulation kernel remains authoritative. Providers may only select from the
legal actions supplied by the server; their response is validated before it is
returned to the orchestration layer.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from .models import RuntimeProfile


class RuntimeProviderError(ValueError):
    pass


def _legal_action_index(payload: Any, legal_actions: list[dict[str, Any]]) -> int | None:
    if isinstance(payload, dict):
        index = payload.get("action_index")
        if isinstance(index, int) and 0 <= index < len(legal_actions):
            return index
        action = payload.get("action", payload)
        if isinstance(action, dict):
            for candidate_index, candidate in enumerate(legal_actions):
                if action == candidate:
                    return candidate_index
            kind = action.get("kind")
            if isinstance(kind, str):
                for candidate_index, candidate in enumerate(legal_actions):
                    if candidate.get("kind") == kind:
                        return candidate_index
    return None


def _parse_json_content(content: str) -> Any:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        start, end = value.find("{"), value.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(value[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise RuntimeProviderError("Provider returned invalid JSON") from error


class MockRuntimeProvider:
    name = "mock"

    def decide(
        self,
        *,
        character_id: str,
        legal_actions: list[dict[str, Any]],
        requested_action: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del context
        legal_kinds = {str(action.get("kind")) for action in legal_actions}
        if requested_action and str(requested_action.get("kind")) in legal_kinds:
            return {
                "character_id": character_id,
                "action": requested_action,
                "source": "mock",
                "accepted": True,
                "model_id": "deterministic-v1",
            }
        fallback = next((action for action in legal_actions if action.get("kind") == "wait"), None)
        if fallback is None:
            fallback = legal_actions[0] if legal_actions else {"kind": "wait"}
        return {
            "character_id": character_id,
            "action": fallback,
            "source": "mock",
            "accepted": False,
            "model_id": "deterministic-v1",
        }


@dataclass(frozen=True)
class OpenAICompatibleSettings:
    provider: str
    base_url: str
    api_key: str


class OpenAICompatibleRuntimeProvider:
    def __init__(
        self,
        profile: RuntimeProfile,
        settings: OpenAICompatibleSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        if not settings.api_key:
            raise RuntimeProviderError(f"No credential is configured for provider {settings.provider}")
        if not settings.base_url:
            raise RuntimeProviderError(f"No API base URL is configured for provider {settings.provider}")
        self.profile = profile
        self.settings = settings
        self.transport = transport

    def _request(self, model_id: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": self.profile.temperature,
            "max_tokens": self.profile.max_tokens,
            "stream": False,
        }
        if self.profile.supports_structured_output:
            body["response_format"] = {"type": "json_object"}
        endpoint = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                timeout=self.profile.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(endpoint, headers=headers, json=body)
                if response.status_code in {400, 422} and "response_format" in body:
                    compatibility_body = {key: value for key, value in body.items() if key != "response_format"}
                    response = client.post(endpoint, headers=headers, json=compatibility_body)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeProviderError(
                f"{self.settings.provider} request failed without exposing the credential"
            ) from error
        if not isinstance(payload, dict):
            raise RuntimeProviderError("Provider response was not an object")
        return payload

    def decide(
        self,
        *,
        character_id: str,
        legal_actions: list[dict[str, Any]],
        requested_action: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not legal_actions:
            raise RuntimeProviderError("At least one legal action is required")
        action_lines = "\n".join(
            f"{index}: {json.dumps(action, ensure_ascii=False, sort_keys=True)}"
            for index, action in enumerate(legal_actions)
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You choose one legal action for an adult fictional character in a mystery simulation. "
                    "The Python simulation is authoritative. Never invent an action. Return JSON only as "
                    '{"action_index": <integer>, "reason": "brief explanation"}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Character: {character_id}\n"
                    f"Context: {json.dumps(context or {}, ensure_ascii=False, sort_keys=True)}\n"
                    f"Requested action: {json.dumps(requested_action, ensure_ascii=False, sort_keys=True)}\n"
                    f"Legal actions:\n{action_lines}"
                ),
            },
        ]
        models = [self.profile.model_id]
        if self.profile.fallback_model_id and self.profile.fallback_model_id not in models:
            models.append(self.profile.fallback_model_id)

        last_error: RuntimeProviderError | None = None
        for model_id in models:
            for _attempt in range(self.profile.retry_count + 1):
                try:
                    payload = self._request(model_id, messages)
                    choices = payload.get("choices")
                    if not isinstance(choices, list) or not choices:
                        raise RuntimeProviderError("Provider returned no choices")
                    message = choices[0].get("message", {})
                    content = message.get("content") if isinstance(message, dict) else None
                    if not isinstance(content, str):
                        raise RuntimeProviderError("Provider returned no message content")
                    parsed = _parse_json_content(content)
                    action_index = _legal_action_index(parsed, legal_actions)
                    if action_index is None:
                        raise RuntimeProviderError("Provider selected an action outside the legal set")
                    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
                    reason = parsed.get("reason") if isinstance(parsed, dict) else None
                    return {
                        "character_id": character_id,
                        "action": legal_actions[action_index],
                        "source": self.settings.provider,
                        "accepted": True,
                        "model_id": model_id,
                        "reason": reason if isinstance(reason, str) else "Provider selected a legal action.",
                        "usage": usage,
                    }
                except RuntimeProviderError as error:
                    last_error = error
        raise last_error or RuntimeProviderError("Provider failed to select a legal action")


def provider_settings(provider: str, secret: str) -> OpenAICompatibleSettings:
    normalized = provider.lower().strip()
    if normalized == "deepseek":
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    elif normalized == "openai":
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    elif normalized == "openai_compatible":
        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "")
    else:
        raise RuntimeProviderError(f"Unsupported runtime provider: {provider}")
    return OpenAICompatibleSettings(provider=normalized, base_url=base_url, api_key=secret)


def provider_for(
    profile: RuntimeProfile | str,
    credential_secret: str | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
):
    # Preserve the original MVP helper shape for tests and callers that only
    # request the deterministic adapter by name.
    if isinstance(profile, str):
        if profile == "mock":
            return MockRuntimeProvider()
        raise RuntimeProviderError(f"Unsupported runtime provider: {profile}")
    if profile.provider == "mock":
        return MockRuntimeProvider()
    settings = provider_settings(profile.provider, credential_secret or "")
    return OpenAICompatibleRuntimeProvider(profile, settings, transport=transport)
