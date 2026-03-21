from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import AppSecret
from app.services import secret_store_service


def test_secret_store_roundtrip() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        secret_store_service.set_secret(db, key="k1", value="value1")
        value = secret_store_service.get_secret(db, key="k1")
        assert value == "value1"
    finally:
        db.close()
        engine.dispose()


def test_secret_store_invalid_ciphertext_returns_none() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        db.add(AppSecret(key="bad", value_encrypted="not-valid-token"))
        db.commit()

        value = secret_store_service.get_secret(db, key="bad")
        assert value is None

        exists = db.scalar(select(AppSecret).where(AppSecret.key == "bad"))
        assert exists is not None
    finally:
        db.close()
        engine.dispose()
