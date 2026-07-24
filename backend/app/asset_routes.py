from __future__ import annotations

import re
from pathlib import PurePath
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .database import get_session
from .models import AssetObject, AssetStatus, User, Visibility
from .schemas import AssetCompleteRequest, AssetPresignRequest
from .storage_service import (
    S3ObjectStorage,
    StorageConfigurationError,
    StorageOperationError,
    storage_health,
    storage_settings,
)

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _safe_filename(filename: str) -> str:
    name = PurePath(filename).name
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-.")
    return cleaned[:180] or "asset.bin"


def _view(asset: AssetObject) -> dict:
    return {
        "id": asset.id,
        "owner_id": asset.owner_id,
        "object_key": asset.object_key,
        "filename": asset.filename,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "visibility": asset.visibility.value,
        "status": asset.status.value,
        "etag": asset.etag,
        "created_at": asset.created_at.isoformat(),
    }


def _storage() -> S3ObjectStorage:
    try:
        return S3ObjectStorage()
    except StorageConfigurationError as error:
        raise HTTPException(503, str(error)) from error


@router.get("/status")
def status() -> dict:
    settings = storage_settings()
    return {
        **storage_health(),
        "endpoint": settings.public_endpoint or None,
        "signed_url_ttl_seconds": settings.signed_url_ttl_seconds,
    }


@router.post("/presign-upload", status_code=201)
def presign_upload(
    payload: AssetPresignRequest,
    owner_id: str,
    session: Session = Depends(get_session),
) -> dict:
    if not session.get(User, owner_id):
        raise HTTPException(404, "owner not found")
    filename = _safe_filename(payload.filename)
    object_key = f"users/{owner_id}/{uuid4()}/{filename}"
    asset = AssetObject(
        owner_id=owner_id,
        object_key=object_key,
        filename=filename,
        content_type=payload.content_type,
        visibility=payload.visibility,
        status=AssetStatus.PENDING,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    try:
        upload_url = _storage().presign_upload(object_key, payload.content_type)
    except StorageOperationError as error:
        asset.status = AssetStatus.FAILED
        session.commit()
        raise HTTPException(502, str(error)) from error
    return {
        "asset": _view(asset),
        "upload": {
            "method": "PUT",
            "url": upload_url,
            "headers": {"Content-Type": payload.content_type},
            "expires_in": storage_settings().signed_url_ttl_seconds,
        },
    }


@router.post("/{asset_id}/complete")
def complete_upload(
    asset_id: str,
    payload: AssetCompleteRequest,
    owner_id: str,
    session: Session = Depends(get_session),
) -> dict:
    asset = session.get(AssetObject, asset_id)
    if not asset or asset.owner_id != owner_id:
        raise HTTPException(404, "asset not found")
    try:
        metadata = _storage().head(asset.object_key)
    except StorageOperationError as error:
        asset.status = AssetStatus.FAILED
        session.commit()
        raise HTTPException(422, str(error)) from error
    size = int(metadata.get("ContentLength", 0))
    if payload.expected_size_bytes is not None and payload.expected_size_bytes != size:
        asset.status = AssetStatus.FAILED
        session.commit()
        raise HTTPException(422, "uploaded object size does not match the expected size")
    remote_content_type = metadata.get("ContentType")
    if remote_content_type and remote_content_type != asset.content_type:
        asset.status = AssetStatus.FAILED
        session.commit()
        raise HTTPException(422, "uploaded object content type does not match the signed request")
    asset.size_bytes = size
    asset.etag = str(metadata.get("ETag", "")).strip('"') or None
    asset.status = AssetStatus.READY
    session.commit()
    return _view(asset)


@router.get("")
def list_assets(owner_id: str, session: Session = Depends(get_session)) -> list[dict]:
    assets = (
        session.query(AssetObject)
        .filter_by(owner_id=owner_id)
        .order_by(AssetObject.created_at.desc())
        .all()
    )
    return [_view(asset) for asset in assets]


@router.get("/{asset_id}/download")
def download(
    asset_id: str,
    viewer_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    asset = session.get(AssetObject, asset_id)
    if not asset or asset.status is not AssetStatus.READY:
        raise HTTPException(404, "asset not found")
    if asset.visibility is Visibility.PRIVATE and viewer_id != asset.owner_id:
        raise HTTPException(403, "private asset")
    try:
        url = _storage().presign_download(asset.object_key, asset.filename)
    except StorageOperationError as error:
        raise HTTPException(502, str(error)) from error
    return {
        "url": url,
        "expires_in": storage_settings().signed_url_ttl_seconds,
        "asset": _view(asset),
    }


@router.delete("/{asset_id}", status_code=204)
def delete_asset(
    asset_id: str,
    owner_id: str,
    session: Session = Depends(get_session),
) -> Response:
    asset = session.get(AssetObject, asset_id)
    if not asset or asset.owner_id != owner_id:
        raise HTTPException(404, "asset not found")
    try:
        _storage().delete(asset.object_key)
    except StorageOperationError as error:
        raise HTTPException(502, str(error)) from error
    session.delete(asset)
    session.commit()
    return Response(status_code=204)
