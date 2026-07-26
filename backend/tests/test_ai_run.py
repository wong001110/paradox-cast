from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai_lobby_routes import set_host_funded_ai_binding
from app.ai_run import run_manifest_with_ai
from app.database import Base
from app.models import (
    CharacterCard,
    FundingModel,
    Lobby,
    LobbyMember,
    LobbyRole,
    LobbyStatus,
    RunManifest,
    RuntimeProfile,
    Scenario,
    ScenarioLocation,
    ScenarioRoute,
    User,
    Visibility,
)
from app.schemas import LobbyBindingUpdate


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_host_funded_runtime_flows_from_lobby_to_ai_replay() -> None:
    with _session() as session:
        host = User(id="host", display_name="Host")
        guest = User(id="guest", display_name="Guest")
        runtime = RuntimeProfile(
            id="runtime",
            owner_id=host.id,
            display_name="Host Mock",
            provider="mock",
            model_id="deterministic-v1",
            temperature=0.2,
            max_tokens=200,
            timeout_seconds=10,
            retry_count=0,
            supports_structured_output=True,
        )
        host_card = CharacterCard(
            id="host-card",
            owner_id=host.id,
            name="Hana",
            adult_age=23,
            profile={"style": "observer"},
            visibility=Visibility.PRIVATE,
        )
        guest_card = CharacterCard(
            id="guest-card",
            owner_id=guest.id,
            name="Rei",
            adult_age=25,
            profile={"style": "reasoner"},
            visibility=Visibility.PRIVATE,
        )
        scenario = Scenario(
            id="scenario",
            owner_id=host.id,
            title="Test Mystery",
            synopsis="A deterministic AI test.",
            world={"evidence": ["A ticket carries the wrong date."]},
            visibility=Visibility.PRIVATE,
        )
        session.add_all(
            [
                host,
                guest,
                runtime,
                host_card,
                guest_card,
                scenario,
                ScenarioLocation(scenario_id=scenario.id, key="lounge", name="Lounge"),
                ScenarioLocation(scenario_id=scenario.id, key="station", name="Station"),
                ScenarioRoute(
                    scenario_id=scenario.id,
                    from_location_key="lounge",
                    to_location_key="station",
                    travel_seconds=300,
                ),
            ]
        )
        lobby = Lobby(
            id="lobby",
            host_id=host.id,
            scenario_id=scenario.id,
            join_code="TESTCODE",
            visibility=Visibility.UNLISTED,
            status=LobbyStatus.OPEN,
            rules={"memory_editing": "forbidden"},
        )
        host_member = LobbyMember(
            id="host-member",
            lobby_id=lobby.id,
            user_id=host.id,
            role=LobbyRole.HOST,
            funding_model=FundingModel.HOST,
        )
        guest_member = LobbyMember(
            id="guest-member",
            lobby_id=lobby.id,
            user_id=guest.id,
            role=LobbyRole.PARTICIPANT,
            funding_model=FundingModel.HOST,
        )
        session.add_all([lobby, host_member, guest_member])
        session.commit()

        set_host_funded_ai_binding(
            lobby.id,
            LobbyBindingUpdate(
                cast_slot="1",
                character_card_id=host_card.id,
                runtime_profile_id=runtime.id,
                funding_model=FundingModel.HOST,
            ),
            host.id,
            session,
        )
        result = set_host_funded_ai_binding(
            lobby.id,
            LobbyBindingUpdate(
                cast_slot="2",
                character_card_id=guest_card.id,
                runtime_profile_id=None,
                funding_model=FundingModel.HOST,
            ),
            guest.id,
            session,
        )
        assert all(member["runtime_profile_id"] == runtime.id for member in result["members"])

        for member in session.query(LobbyMember).filter_by(lobby_id=lobby.id).all():
            member.ready = True
        manifest = RunManifest(
            id="manifest",
            lobby_id=lobby.id,
            scenario_version=scenario.version,
            cast=[
                {"slot": "1", "user_id": host.id, "character_card_id": host_card.id, "character_version": 1},
                {"slot": "2", "user_id": guest.id, "character_card_id": guest_card.id, "character_version": 1},
            ],
            runtime_bindings=[
                {"slot": "1", "runtime_profile_id": runtime.id, "provider": "mock", "model_id": runtime.model_id},
                {"slot": "2", "runtime_profile_id": runtime.id, "provider": "mock", "model_id": runtime.model_id},
            ],
            rules=lobby.rules,
            seed=1404,
            asset_versions={},
            intervention_rules={"allowed": ["delay_information"]},
        )
        lobby.status = LobbyStatus.RUNNING
        session.add(manifest)
        session.commit()

        run = run_manifest_with_ai(session, manifest, turns=2)

        assert run["case"]["mode"] == "ai"
        assert run["case"]["fallback_used"] is False
        assert len(run["decisions"]) == 4
        assert all(decision["runtime_profile_id"] == runtime.id for decision in run["decisions"])
        assert any(event["details"].get("source") == "mock" for event in run["original"]["events"])
        assert run["branched"]["interventions"][0]["kind"] == "delay_information"
