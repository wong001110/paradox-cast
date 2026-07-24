"""Server-side credential handling.

Plaintext API keys enter only through the create route, are encrypted before persistence,
and are never returned by API schemas.  Production must configure a stable Fernet key.
"""
from __future__ import annotations

import os
from cryptography.fernet import Fernet


_ephemeral_key = Fernet.generate_key()


def _fernet() -> Fernet:
    key = os.getenv("PARADOX_CAST_CREDENTIAL_KEY")
    # A generated process-local key is deliberately development-only: it avoids
    # plaintext storage but makes credentials unusable after a restart.
    return Fernet(key.encode() if key else _ephemeral_key)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")


def mask_secret(secret: str) -> str:
    suffix = secret[-4:] if len(secret) >= 4 else ""
    return f"••••{suffix}" if suffix else "••••"
