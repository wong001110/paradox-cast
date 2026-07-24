from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .credential_service import encrypt_secret, mask_secret
from .database import get_session
from .models import Credential, RuntimeProfile
from .runtime_service import provider_for
from .schemas import CredentialCreate, MockDecisionRequest, RuntimeProfileCreate

router = APIRouter(tags=["runtimes", "credentials"])


def credential_view(credential: Credential) -> dict:
    return {"id": credential.id, "provider": credential.provider, "label": credential.label, "masked_identifier": credential.masked_identifier}


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


@router.post("/api/credentials", status_code=201)
def create_credential(payload: CredentialCreate, owner_id: str, session: Session = Depends(get_session)) -> dict:
    secret = payload.api_secret.get_secret_value()
    if not secret:
        raise HTTPException(422, "api_secret must not be blank")
    credential = Credential(
        owner_id=owner_id,
        provider=payload.provider,
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
    return [credential_view(item) for item in session.query(Credential).filter_by(owner_id=owner_id).all()]


@router.delete("/api/credentials/{credential_id}", status_code=204)
def delete_credential(credential_id: str, owner_id: str, session: Session = Depends(get_session)) -> None:
    credential = session.get(Credential, credential_id)
    if not credential or credential.owner_id != owner_id:
        raise HTTPException(404, "credential not found")
    if session.query(RuntimeProfile).filter_by(credential_id=credential_id).first():
        raise HTTPException(409, "credential is still bound to a runtime profile")
    session.delete(credential)
    session.commit()


@router.post("/api/runtimes", status_code=201)
def create_runtime(payload: RuntimeProfileCreate, owner_id: str, session: Session = Depends(get_session)) -> dict:
    if payload.credential_id:
        credential = session.get(Credential, payload.credential_id)
        if not credential or credential.owner_id != owner_id:
            raise HTTPException(422, "credential does not belong to this user")
    profile = RuntimeProfile(owner_id=owner_id, **payload.model_dump())
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return runtime_view(profile)


@router.get("/api/runtimes")
def list_runtimes(owner_id: str, session: Session = Depends(get_session)) -> list[dict]:
    return [runtime_view(item) for item in session.query(RuntimeProfile).filter_by(owner_id=owner_id).all()]


@router.post("/api/runtimes/{runtime_id}/decide")
def mock_decide(runtime_id: str, payload: MockDecisionRequest, owner_id: str, session: Session = Depends(get_session)) -> dict:
    profile = session.get(RuntimeProfile, runtime_id)
    if not profile or profile.owner_id != owner_id:
        raise HTTPException(404, "runtime profile not found")
    try:
        provider = provider_for(profile.provider)
    except ValueError as error:
        raise HTTPException(501, str(error)) from error
    return provider.decide(
        character_id=payload.character_id,
        legal_actions=payload.legal_actions,
        requested_action=payload.requested_action,
    )
