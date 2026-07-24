import enum
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def uid() -> str: return str(uuid4())
def now() -> datetime: return datetime.utcnow()

class Visibility(str, enum.Enum): PRIVATE="private"; UNLISTED="unlisted"; PUBLIC="public"
class LobbyRole(str, enum.Enum): HOST="host"; PARTICIPANT="participant"; SPECTATOR="spectator"
class LobbyStatus(str, enum.Enum): OPEN="open"; LOCKED="locked"; RUNNING="running"; CLOSED="closed"
class FundingModel(str, enum.Enum): HOST="host_funded"; BYO="bring_your_own"

class User(Base):
    __tablename__="users"; id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); display_name: Mapped[str]=mapped_column(String(120)); is_admin: Mapped[bool]=mapped_column(Boolean,default=False); created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
class CharacterCard(Base):
    __tablename__="character_cards"; id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); owner_id: Mapped[str]=mapped_column(ForeignKey("users.id")); name: Mapped[str]=mapped_column(String(120)); adult_age: Mapped[int]=mapped_column(Integer); biography: Mapped[str]=mapped_column(Text,default=""); profile: Mapped[dict]=mapped_column(JSON,default=dict); visual_assets: Mapped[dict]=mapped_column(JSON,default=dict); default_runtime_id: Mapped[str|None]=mapped_column(ForeignKey("runtime_profiles.id"),nullable=True); visibility: Mapped[Visibility]=mapped_column(Enum(Visibility),default=Visibility.PRIVATE); version: Mapped[int]=mapped_column(Integer,default=1); forked_from_id: Mapped[str|None]=mapped_column(String,nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
class Scenario(Base):
    __tablename__="scenarios"; id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); owner_id: Mapped[str]=mapped_column(ForeignKey("users.id")); title: Mapped[str]=mapped_column(String(160)); synopsis: Mapped[str]=mapped_column(Text,default=""); world: Mapped[dict]=mapped_column(JSON,default=dict); version: Mapped[int]=mapped_column(Integer,default=1); visibility: Mapped[Visibility]=mapped_column(Enum(Visibility),default=Visibility.PRIVATE)
class RuntimeProfile(Base):
    __tablename__="runtime_profiles"; id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); owner_id: Mapped[str]=mapped_column(ForeignKey("users.id")); display_name: Mapped[str]=mapped_column(String(120)); provider: Mapped[str]=mapped_column(String(80)); model_id: Mapped[str]=mapped_column(String(160)); temperature: Mapped[float]=mapped_column(Float,default=.7); max_tokens: Mapped[int]=mapped_column(Integer,default=600); timeout_seconds: Mapped[int]=mapped_column(Integer,default=30); retry_count: Mapped[int]=mapped_column(Integer,default=1); fallback_model_id: Mapped[str|None]=mapped_column(String(160),nullable=True); supports_structured_output: Mapped[bool]=mapped_column(Boolean,default=True)
class Credential(Base):
    __tablename__="credentials"; id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); owner_id: Mapped[str]=mapped_column(ForeignKey("users.id")); provider: Mapped[str]=mapped_column(String(80)); label: Mapped[str]=mapped_column(String(120)); secret_ciphertext: Mapped[str]=mapped_column(Text); masked_identifier: Mapped[str]=mapped_column(String(32)); created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
class Lobby(Base):
    __tablename__="lobbies"; id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); host_id: Mapped[str]=mapped_column(ForeignKey("users.id")); scenario_id: Mapped[str]=mapped_column(ForeignKey("scenarios.id")); join_code: Mapped[str]=mapped_column(String(12),unique=True); visibility: Mapped[Visibility]=mapped_column(Enum(Visibility)); status: Mapped[LobbyStatus]=mapped_column(Enum(LobbyStatus),default=LobbyStatus.OPEN); rules: Mapped[dict]=mapped_column(JSON,default=dict)
class RunManifest(Base):
    __tablename__="run_manifests"; id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); lobby_id: Mapped[str]=mapped_column(ForeignKey("lobbies.id"),unique=True); scenario_version: Mapped[int]=mapped_column(Integer); cast: Mapped[list]=mapped_column(JSON); runtime_bindings: Mapped[list]=mapped_column(JSON); rules: Mapped[dict]=mapped_column(JSON); seed: Mapped[int]=mapped_column(Integer); asset_versions: Mapped[dict]=mapped_column(JSON); intervention_rules: Mapped[dict]=mapped_column(JSON); frozen_at: Mapped[datetime]=mapped_column(DateTime,default=now)
