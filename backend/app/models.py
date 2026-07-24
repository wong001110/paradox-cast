from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def uid() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Visibility(str, enum.Enum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class LobbyRole(str, enum.Enum):
    HOST = "host"
    PARTICIPANT = "participant"
    SPECTATOR = "spectator"


class LobbyStatus(str, enum.Enum):
    OPEN = "open"
    LOCKED = "locked"
    RUNNING = "running"
    CLOSED = "closed"


class FundingModel(str, enum.Enum):
    HOST = "host_funded"
    BYO = "bring_your_own"


class AssetStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    display_name: Mapped[str] = mapped_column(String(120))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(120))
    secret_ciphertext: Mapped[str] = mapped_column(Text)
    masked_identifier: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RuntimeProfile(Base):
    __tablename__ = "runtime_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(80))
    model_id: Mapped[str] = mapped_column(String(160))
    credential_id: Mapped[str | None] = mapped_column(ForeignKey("credentials.id"), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=600)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    retry_count: Mapped[int] = mapped_column(Integer, default=1)
    fallback_model_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    supports_structured_output: Mapped[bool] = mapped_column(Boolean, default=True)


class CharacterCard(Base):
    __tablename__ = "character_cards"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    adult_age: Mapped[int] = mapped_column(Integer)
    biography: Mapped[str] = mapped_column(Text, default="")
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    visual_assets: Mapped[dict] = mapped_column(JSON, default=dict)
    default_runtime_id: Mapped[str | None] = mapped_column(ForeignKey("runtime_profiles.id"), nullable=True)
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility), default=Visibility.PRIVATE)
    version: Mapped[int] = mapped_column(Integer, default=1)
    forked_from_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    synopsis: Mapped[str] = mapped_column(Text, default="")
    world: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility), default=Visibility.PRIVATE)


class ScenarioLocation(Base):
    __tablename__ = "scenario_locations"
    __table_args__ = (UniqueConstraint("scenario_id", "key", name="uq_scenario_location_key"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ScenarioRoute(Base):
    __tablename__ = "scenario_routes"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "from_location_key",
            "to_location_key",
            name="uq_scenario_route_direction",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    from_location_key: Mapped[str] = mapped_column(String(80))
    to_location_key: Mapped[str] = mapped_column(String(80))
    travel_seconds: Mapped[int] = mapped_column(Integer)
    route_type: Mapped[str] = mapped_column(String(40), default="walk")
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)


class Lobby(Base):
    __tablename__ = "lobbies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    host_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    join_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility))
    status: Mapped[LobbyStatus] = mapped_column(Enum(LobbyStatus), default=LobbyStatus.OPEN)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)


class LobbyMember(Base):
    __tablename__ = "lobby_members"
    __table_args__ = (
        UniqueConstraint("lobby_id", "user_id", name="uq_lobby_member_user"),
        UniqueConstraint("lobby_id", "cast_slot", name="uq_lobby_cast_slot"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    lobby_id: Mapped[str] = mapped_column(ForeignKey("lobbies.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[LobbyRole] = mapped_column(Enum(LobbyRole), default=LobbyRole.PARTICIPANT)
    cast_slot: Mapped[str | None] = mapped_column(String(80), nullable=True)
    character_card_id: Mapped[str | None] = mapped_column(ForeignKey("character_cards.id"), nullable=True)
    runtime_profile_id: Mapped[str | None] = mapped_column(ForeignKey("runtime_profiles.id"), nullable=True)
    funding_model: Mapped[FundingModel] = mapped_column(Enum(FundingModel), default=FundingModel.HOST)
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class LobbyInvitation(Base):
    __tablename__ = "lobby_invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    lobby_id: Mapped[str] = mapped_column(ForeignKey("lobbies.id"), index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    role: Mapped[LobbyRole] = mapped_column(Enum(LobbyRole), default=LobbyRole.PARTICIPANT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RunManifest(Base):
    __tablename__ = "run_manifests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    lobby_id: Mapped[str] = mapped_column(ForeignKey("lobbies.id"), unique=True, index=True)
    scenario_version: Mapped[int] = mapped_column(Integer)
    cast: Mapped[list] = mapped_column(JSON)
    runtime_bindings: Mapped[list] = mapped_column(JSON)
    rules: Mapped[dict] = mapped_column(JSON)
    seed: Mapped[int] = mapped_column(Integer)
    asset_versions: Mapped[dict] = mapped_column(JSON)
    intervention_rules: Mapped[dict] = mapped_column(JSON)
    frozen_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AssetObject(Base):
    __tablename__ = "asset_objects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility), default=Visibility.PRIVATE)
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.PENDING)
    etag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
