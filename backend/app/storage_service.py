"""Cloudflare R2 / S3-compatible object storage boundary.

The same adapter targets Cloudflare R2 in deployed environments and MinIO in the
local Docker stack. Credentials stay server-side; browsers receive only short-lived
presigned URLs for a single object operation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError


class StorageConfigurationError(RuntimeError):
    pass


class StorageOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class StorageSettings:
    endpoint: str
    public_endpoint: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    region: str
    signed_url_ttl_seconds: int
    auto_create_bucket: bool
    addressing_style: str

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.bucket and self.access_key_id and self.secret_access_key)


@lru_cache(maxsize=1)
def storage_settings() -> StorageSettings:
    endpoint = os.getenv("R2_ENDPOINT", "").rstrip("/")
    return StorageSettings(
        endpoint=endpoint,
        public_endpoint=os.getenv("R2_PUBLIC_ENDPOINT", endpoint).rstrip("/"),
        bucket=os.getenv("R2_BUCKET_NAME", ""),
        access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
        secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
        region=os.getenv("R2_REGION", "auto"),
        signed_url_ttl_seconds=max(1, min(604_800, int(os.getenv("R2_SIGNED_URL_TTL_SECONDS", "300")))),
        auto_create_bucket=os.getenv("R2_AUTO_CREATE_BUCKET", "false").lower() in {"1", "true", "yes"},
        addressing_style=os.getenv("R2_ADDRESSING_STYLE", "path"),
    )


def reset_storage_settings_cache() -> None:
    storage_settings.cache_clear()


class S3ObjectStorage:
    def __init__(self, settings: StorageSettings | None = None):
        self.settings = settings or storage_settings()
        if not self.settings.configured:
            raise StorageConfigurationError("R2/S3 object storage is not configured")
        self._client = self._make_client(self.settings.endpoint)
        self._signing_client = self._make_client(self.settings.public_endpoint)
        if self.settings.auto_create_bucket:
            self.ensure_bucket()

    def _make_client(self, endpoint: str):
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=self.settings.access_key_id,
            aws_secret_access_key=self.settings.secret_access_key,
            region_name=self.settings.region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": self.settings.addressing_style},
            ),
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.settings.bucket)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status not in {400, 403, 404}:
                raise StorageOperationError("Could not inspect object-storage bucket") from error
            try:
                self._client.create_bucket(Bucket=self.settings.bucket)
            except (BotoCoreError, ClientError) as create_error:
                raise StorageOperationError("Could not create object-storage bucket") from create_error

    def presign_upload(self, object_key: str, content_type: str) -> str:
        try:
            return self._signing_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.settings.bucket,
                    "Key": object_key,
                    "ContentType": content_type,
                },
                ExpiresIn=self.settings.signed_url_ttl_seconds,
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("Could not create upload URL") from error

    def presign_download(self, object_key: str, filename: str | None = None) -> str:
        params: dict[str, Any] = {"Bucket": self.settings.bucket, "Key": object_key}
        if filename:
            params["ResponseContentDisposition"] = f'inline; filename="{filename.replace(chr(34), "")}"'
        try:
            return self._signing_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=self.settings.signed_url_ttl_seconds,
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("Could not create download URL") from error

    def head(self, object_key: str) -> dict[str, Any]:
        try:
            return self._client.head_object(Bucket=self.settings.bucket, Key=object_key)
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("Uploaded object was not found") from error

    def delete(self, object_key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.settings.bucket, Key=object_key)
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("Could not delete object") from error

    def health(self) -> dict[str, Any]:
        try:
            response = self._client.list_objects_v2(Bucket=self.settings.bucket, MaxKeys=1)
            return {
                "configured": True,
                "reachable": True,
                "bucket": self.settings.bucket,
                "object_count_sample": int(response.get("KeyCount", 0)),
            }
        except (BotoCoreError, ClientError) as error:
            return {
                "configured": True,
                "reachable": False,
                "bucket": self.settings.bucket,
                "error": type(error).__name__,
            }


def storage_health() -> dict[str, Any]:
    settings = storage_settings()
    if not settings.configured:
        return {"configured": False, "reachable": False, "bucket": settings.bucket or None}
    try:
        return S3ObjectStorage(settings).health()
    except StorageConfigurationError:
        return {"configured": False, "reachable": False, "bucket": settings.bucket or None}
