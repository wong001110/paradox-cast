from __future__ import annotations

import os

from fastapi import APIRouter
from sqlalchemy import text

from .database import DATABASE_URL, engine
from .storage_service import storage_health

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
def system_status() -> dict:
    database_reachable = False
    database_error: str | None = None
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_reachable = True
    except Exception as error:  # status endpoint deliberately avoids leaking connection data
        database_error = type(error).__name__
    app_env = os.getenv("APP_ENV", "development")
    configured_local = os.getenv("LOCAL_BOOTSTRAP_ENABLED")
    local_enabled = (
        configured_local.lower() in {"1", "true", "yes"}
        if configured_local is not None
        else app_env.lower() != "production"
    )
    return {
        "app_env": app_env,
        "database": {
            "dialect": engine.url.drivername,
            "configured": bool(DATABASE_URL),
            "reachable": database_reachable,
            "error": database_error,
        },
        "object_storage": storage_health(),
        "credential_encryption": {
            "persistent_key_configured": bool(os.getenv("PARADOX_CAST_CREDENTIAL_KEY")),
        },
        "local_bootstrap_enabled": local_enabled,
    }
