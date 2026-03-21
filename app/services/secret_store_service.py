from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings

settings = get_settings()


def _fernet() -> Fernet:
    # Derive a deterministic key from SIGNING_SECRET so encrypted values stay readable
    # across restarts as long as SIGNING_SECRET is unchanged.
    digest = hashlib.sha256(settings.signing_secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def set_secret(db: Session, *, key: str, value: str) -> None:
    cipher = _fernet()
    encrypted = cipher.encrypt(value.encode("utf-8")).decode("utf-8")

    existing = db.scalar(select(models.AppSecret).where(models.AppSecret.key == key))
    if existing:
        existing.value_encrypted = encrypted
        db.add(existing)
    else:
        db.add(models.AppSecret(key=key, value_encrypted=encrypted))

    db.commit()


def get_secret(db: Session, *, key: str) -> str | None:
    existing = db.scalar(select(models.AppSecret).where(models.AppSecret.key == key))
    if not existing:
        return None

    cipher = _fernet()
    try:
        decrypted = cipher.decrypt(existing.value_encrypted.encode("utf-8"))
    except InvalidToken:
        return None

    return decrypted.decode("utf-8")
