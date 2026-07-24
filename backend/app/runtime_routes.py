from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .credential_service import decrypt_secret, encrypt_secret, mask_secret
from .database import get_session
from .models import Credential, RuntimeProfile
from .runtime_service import RuntimeProviderError, provider_for
from .schemas import CredentialCreate, MockDecisionRequest, RuntimeProfileCreate

router = APIRouter(tags=["runtimes", "credentials"])


def credential_view(credential: Credential) -> dict:
    return {
        "id": credential.id,
        "provider": credential.provider,
        "label": credential.label,
        "masked_identifier": credential.masked_identifier,
    }


def runtime_view(profile: RuntimeProfile) -> dict:
    return {
        "id": profile.id,
        "display_name": profile.display_name,
        "provider": profile.provider,
        "model_id": profile.model_id,
        "credential_id": profile.credential_id,
        "temperature": profile.temperature,
        "max_tokens": profile.max_tokens,
        "timeout_seconds": profile.timeout_seconds,
        "retry_count": profile.retry_count,
        "fallback_model_id": profile.fallback_model_id,
        "supports_structured_output": profile.supports_structured_output,
    }


@router.get("/api/providers")
def providers() -> list[dict]:
    return [
        {"id": "mock", "credential_required": False, "configured": True},
        {
            "id": "deepseek",
            "credential_required": True,
            "configured": bool(os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")),
        },
        {
            "id": "openai",
            "credential_required": True,
            "configured": bool(os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")),
        },
        {
            "id": "openai_compatible",
            "credential_required": True,
            "configured": bool(os.getenv("OPENAI_COMPATIBLE_BASE_URL")),
        },
    ]


@router.post("/api/credentials", status_code=201)
def create_credential(
    payload: CredentialCreate,
    owner_id: str,
    session: Session = Depends(get_session),
) -> dict:
    secret = payload.api_secret.get_secret_value().strip()
    if not secret:
        raise HTTPException(422, "api_secret must not be blank")
    credential = Credential(
        owner_id=owner_id,
        provider=payload.provider.lower().strip(),
        label=payload.label,
        secret_ciphertext=encrypt_secret(secret),
        masked_identifier=mask_secret(secret),
    )
    session.add(credential)
    session.commit()
    session.refresh(credential)
    return credential_view(credential)


@router.get("/api/credentials")
def list_credentials(owner_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [
        credential_view(item)
        for item in session.query(Credential).filter_by(owner_id=owner_id).order_by(Credential.created_at).all()
    ]


@router.delete("/api/credentials/{credential_id}", status_code=204)
def delete_credential(
    credential_id: str,
    owner_id: str,
    session: Session = Depends(get_session),
) -> None:
    credential = session.get(Credential, credential_id)
    if not credential or credential.owner_id != owner_id:
        raise HTTPException(404, "credential not found")
    if session.query(RuntimeProfile).filter_by(credential_id=credential_id).first():
        raise HTTPException(409, "credential is still bound to a runtime profile")
    session.delete(credential)
    session.commit()


@router.post("/api/runtimes", status_code=201)
def create_runtime(
    payload: RuntimeProfileCreate,
    owner_id: str,
    session: Session = Depends(get_session),
) -> dict:
    provider = payload.provider.lower().strip()
    if provider != "mock" and not payload.credential_id:
        raise HTTPException(422, "a credential is required for a network provider")
    if payload.credential_id:
        credential = session.get(Credential, payload.credential_id)
        if not credential or credential.owner_id != owner_id:
            raise HTTPException(422, "credential does not belong to this user")
        if provider != "openai_compatible" and credential.provider != provider:
            raise HTTPException(422, "credential provider does not match the runtime provider")
    profile = RuntimeProfile(owner_id=owner_id, **{**payload.model_dump(), "provider": provider})
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return runtime_view(profile)


@router.get("/api/runtimes")
def list_runtimes(owner_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [
        runtime_view(item)
        for item in session.query(RuntimeProfile).filter_by(owner_id=owner_id).order_by(RuntimeProfile.display_name).all()
    ]


@router.post("/api/runtimes/{runtime_id}/decide")
def decide(
    runtime_id: str,
    payload: MockDecisionRequest,
    owner_id: str,
    session: Session = Depends(get_session),
) -> dict:
    profile = session.get(RuntimeProfile, runtime_id)
    if not profile or profile.owner_id != owner_id:
        raise HTTPException(404, "runtime profile not found")

    secret: str | None = None
    if profile.credential_id:
        credential = session.get(Credential, profile.credential_id)
        if not credential or credential.owner_id != owner_id:
            raise HTTPException(422, "runtime credential is unavailable")
        try:
            secret = decrypt_secret(credential.secret_ciphertext)
        except Exception as error:
            raise HTTPException(
                422,
                "credential could not be decrypted; configure a stable PARADOX_CAST_CREDENTIAL_KEY",
            ) from error

    try:
        provider = provider_for(profile, secret)
        return provider.decide(
            character_id=payload.character_id,
            legal_actions=payload.legal_actions,
            requested_action=payload.requested_action,
            context=payload.context,
        )
    except RuntimeProviderError as error:
        raise HTTPException(502, str(error)) from error
