from __future__ import annotations

import json

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.local_routes import bootstrap
from app.models import RuntimeProfile
from app.runtime_service import OpenAICompatibleRuntimeProvider, OpenAICompatibleSettings
from app.storage_service import S3ObjectStorage, StorageSettings


def test_all_metadata_and_local_bootstrap_are_runnable() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    expected = {
        "users",
        "credentials",
        "runtime_profiles",
        "character_cards",
        "scenarios",
        "scenario_locations",
        "scenario_routes",
        "lobbies",
        "lobby_members",
        "lobby_invitations",
        "run_manifests",
        "asset_objects",
    }
    assert expected.issubset(set(Base.metadata.tables))
    with Session(engine, expire_on_commit=False) as session:
        payload = bootstrap(session)
        assert payload["enabled"] is True
        assert len(payload["users"]) == 3
        assert payload["scenario"]["title"] == "The Vanishing of April 14th"


def test_r2_adapter_generates_single_operation_presigned_urls() -> None:
    settings = StorageSettings(
        endpoint="http://minio:9000",
        public_endpoint="http://localhost:9000",
        bucket="paradox-cast",
        access_key_id="paradox",
        secret_access_key="local-secret",
        region="us-east-1",
        signed_url_ttl_seconds=300,
        auto_create_bucket=False,
        addressing_style="path",
    )
    storage = S3ObjectStorage(settings)
    url = storage.presign_upload("users/test/picture.webp", "image/webp")
    assert url.startswith("http://localhost:9000/paradox-cast/users/test/picture.webp?")
    assert "X-Amz-Signature=" in url


def test_network_provider_must_choose_a_server_supplied_legal_action() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert request.headers["authorization"] == "Bearer secret-value"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"action_index": 1, "reason": "follow evidence"}'}}],
                "usage": {"total_tokens": 12},
            },
        )

    profile = RuntimeProfile(
        owner_id="owner",
        display_name="Test",
        provider="deepseek",
        model_id="test-model",
        temperature=0.2,
        max_tokens=100,
        timeout_seconds=10,
        retry_count=0,
        supports_structured_output=True,
    )
    provider = OpenAICompatibleRuntimeProvider(
        profile,
        OpenAICompatibleSettings(provider="deepseek", base_url="https://api.example.test", api_key="secret-value"),
        transport=httpx.MockTransport(handler),
    )
    legal = [{"kind": "wait"}, {"kind": "move", "destination_id": "station"}]
    result = provider.decide(character_id="hana", legal_actions=legal, context={"location": "lounge"})
    assert result["action"] == legal[1]
    assert result["source"] == "deepseek"
    assert "secret-value" not in json.dumps(result)
