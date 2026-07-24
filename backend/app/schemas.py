from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, model_validator

from .models import FundingModel, LobbyRole, Visibility


class CharacterCreate(BaseModel):
    name: str
    adult_age: int = Field(ge=18, le=120)
    biography: str = ""
    profile: dict = Field(default_factory=dict)
    visual_assets: dict = Field(default_factory=dict)
    visibility: Visibility = Visibility.PRIVATE


class CredentialCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    api_secret: SecretStr


class CredentialView(BaseModel):
    id: str
    provider: str
    label: str
    masked_identifier: str


class RuntimeProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=80)
    model_id: str = Field(min_length=1, max_length=160)
    credential_id: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=600, ge=1, le=32_000)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_count: int = Field(default=1, ge=0, le=5)
    fallback_model_id: str | None = None
    supports_structured_output: bool = True


class LocationNode(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)


class RouteSegment(BaseModel):
    id: str | None = None
    from_location_id: str
    to_location_id: str
    travel_minutes: int = Field(ge=1, le=24 * 60)
    bidirectional: bool = True


class SimulationCharacter(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    initial_location_id: str


class SimulationAction(BaseModel):
    """A high-level intention. The kernel determines whether and how it happens."""

    id: str | None = None
    character_id: str
    kind: Literal["move", "change_destination", "observe", "speak", "intercept", "wait"]
    start_at: int = Field(default=0, ge=0, le=24 * 60)
    destination_id: str | None = None
    target_character_id: str | None = None
    content: str = Field(default="", max_length=2_000)


class SimulationRequest(BaseModel):
    seed: int = Field(default=1, ge=0, le=2**31 - 1)
    locations: list[LocationNode] = Field(min_length=1)
    routes: list[RouteSegment] = Field(default_factory=list)
    characters: list[SimulationCharacter] = Field(min_length=1)
    actions: list[SimulationAction] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "SimulationRequest":
        location_ids = [location.id for location in self.locations]
        character_ids = [character.id for character in self.characters]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("location ids must be unique")
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("character ids must be unique")
        locations, characters = set(location_ids), set(character_ids)
        for character in self.characters:
            if character.initial_location_id not in locations:
                raise ValueError(f"unknown initial location: {character.initial_location_id}")
        for route in self.routes:
            if route.from_location_id not in locations or route.to_location_id not in locations:
                raise ValueError("route references an unknown location")
        for action in self.actions:
            if action.character_id not in characters:
                raise ValueError(f"unknown character: {action.character_id}")
            if action.destination_id is not None and action.destination_id not in locations:
                raise ValueError(f"unknown destination: {action.destination_id}")
            if action.target_character_id is not None and action.target_character_id not in characters:
                raise ValueError(f"unknown target character: {action.target_character_id}")
        return self


class MockDecisionRequest(BaseModel):
    character_id: str
    legal_actions: list[dict[str, Any]] = Field(default_factory=list)
    requested_action: dict[str, Any] | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ScenarioLocationInput(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    metadata: dict = Field(default_factory=dict)


class ScenarioRouteInput(BaseModel):
    from_location_key: str = Field(min_length=1, max_length=80)
    to_location_key: str = Field(min_length=1, max_length=80)
    travel_seconds: int = Field(gt=0, le=86_400)
    route_type: str = Field(default="walk", min_length=1, max_length=40)
    constraints: dict = Field(default_factory=dict)


class ScenarioCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    synopsis: str = ""
    world: dict = Field(default_factory=dict)
    visibility: Visibility = Visibility.PRIVATE
    locations: list[ScenarioLocationInput] = Field(default_factory=list)
    routes: list[ScenarioRouteInput] = Field(default_factory=list)


class LobbyCreate(BaseModel):
    scenario_id: str
    visibility: Visibility = Visibility.PRIVATE
    rules: dict = Field(default_factory=dict)


class LobbyJoin(BaseModel):
    join_code: str = Field(min_length=4, max_length=12)
    role: LobbyRole = LobbyRole.PARTICIPANT


class LobbyBindingUpdate(BaseModel):
    cast_slot: str | None = Field(default=None, max_length=80)
    character_card_id: str | None = None
    runtime_profile_id: str | None = None
    funding_model: FundingModel = FundingModel.HOST


class LobbyReadyUpdate(BaseModel):
    ready: bool


class LobbyInviteCreate(BaseModel):
    recipient_id: str | None = None
    role: LobbyRole = LobbyRole.PARTICIPANT


class ManifestStartRequest(BaseModel):
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    intervention_rules: dict = Field(default_factory=dict)


class BranchReplayRequest(BaseModel):
    simulation: SimulationRequest
    interventions: list[dict] = Field(default_factory=list)


class AssetPresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=160)
    visibility: Visibility = Visibility.PRIVATE


class AssetCompleteRequest(BaseModel):
    expected_size_bytes: int | None = Field(default=None, ge=0)
