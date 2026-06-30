"""Database layer for the secure chat prototype.

Storage uses SQLAlchemy so the same code runs on SQLite locally and PostgreSQL
in deployment. Pick the backend with one env var:

    DATABASE_URL=sqlite:///./data/secure_chat.db        # local default
    DATABASE_URL=postgresql://user:pass@host:5432/db     # managed Postgres

When DATABASE_URL is unset the server falls back to a SQLite file under
SECURE_CHAT_DATA_DIR (default ./data). Heroku-style "postgres://" URLs are
normalised automatically.

Schema design notes
-------------------
* Real foreign keys with ON DELETE rules enforce referential integrity
  (SQLite needs PRAGMA foreign_keys=ON, set on every connection below).
* Timestamps are stored as timezone-aware DateTime columns, not strings, so the
  database can sort/range-query them. API responses still serialise them to the
  ISO strings / epoch seconds the frontend expects (see each as_dict()).
* Conversations are normalised into their own table; messages carry an indexed
  conversation_id / message_number instead of hiding them inside the JSON packet.
* Schema changes are managed by Alembic migrations (see ./migrations). init_db()
  / reset_db() (create_all) remain as a zero-config path for local dev and tests.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("SECURE_CHAT_DATA_DIR", ROOT_DIR / "data"))


def _normalize_database_url(raw: str | None) -> str:
    if not raw:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(DATA_DIR / 'secure_chat.db').as_posix()}"
    url = raw.strip()
    # SQLAlchemy 2.x needs an explicit driver for the psycopg 3 dialect.
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL"))
IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_MEMORY = IS_SQLITE and ":memory:" in DATABASE_URL

_engine_kwargs: dict[str, Any] = {"pool_pre_ping": True, "future": True}
if IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    if IS_MEMORY:
        # Keep one shared in-memory connection across threads (used by tests).
        _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")  # enforce FKs (off by default)
        cursor.close()


# --- timestamp helpers: store native datetimes, serialise to legacy formats ---

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def iso(value: datetime | None) -> str | None:
    aware = _as_utc(value)
    return aware.isoformat() if aware is not None else None


def epoch(value: datetime | None) -> int | None:
    aware = _as_utc(value)
    return int(aware.timestamp()) if aware is not None else None


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signing_public_key: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    devices: Mapped[list["Device"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    sessions: Mapped[list["RefreshSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "password_hash": self.password_hash,
            "is_admin": self.is_admin,
            "signing_public_key": self.signing_public_key,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "refresh_token_hash": self.refresh_token_hash,
            "created_at": iso(self.created_at),
            "expires_at": epoch(self.expires_at),  # frontend multiplies by 1000
            "revoked_at": iso(self.revoked_at),
        }


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_label: Mapped[str] = mapped_column(String(80), nullable=False)
    identity_public_key: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    device_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="devices")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_label": self.device_label,
            "identity_public_key": self.identity_public_key,
            "fingerprint": self.fingerprint,
            "device_signature": self.device_signature,
            "created_at": iso(self.created_at),
            "last_seen_at": iso(self.last_seen_at),
            "revoked_at": iso(self.revoked_at),
        }


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    participant_a: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    participant_b: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "participant_a": self.participant_a,
            "participant_b": self.participant_b,
            "created_at": iso(self.created_at),
            "last_message_at": iso(self.last_message_at),
        }


class Message(Base):
    __tablename__ = "messages"

    # seq is an autoincrement surrogate that preserves insertion order; id is the
    # public message token used by the API and the Security Lab lookups.
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    conversation_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    recipient_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_number: Mapped[int] = mapped_column(Integer, nullable=False)
    packet: Mapped[dict] = mapped_column(JSON, nullable=False)
    server_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "sender_user_id": self.sender_user_id,
            "recipient_user_id": self.recipient_user_id,
            "message_number": self.message_number,
            "packet": self.packet,
            "server_received_at": iso(self.server_received_at),
            "delivered_at": iso(self.delivered_at),
        }


class SecurityEvent(Base):
    __tablename__ = "security_events"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    # Keep audit rows even if the actor account is deleted (SET NULL, not CASCADE).
    actor_user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    actor_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "actor_user_id": self.actor_user_id,
            "actor_ip": self.actor_ip,
            "actor_user_agent": self.actor_user_agent,
            "detail": self.detail,
            "created_at": iso(self.created_at),
        }



class PreKey(Base):
    __tablename__ = "pre_keys"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(80), nullable=False)
    key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    public_key_jwk: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    is_otp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "key_id": self.key_id,
            "public_key_jwk": self.public_key_jwk,
            "fingerprint": self.fingerprint,
            "signature": self.signature,
            "is_otp": self.is_otp,
            "consumed_at": iso(self.consumed_at),
            "created_at": iso(self.created_at),
        }


def safe_database_label() -> str:
    """Connection string with any password redacted, safe to show in the UI."""
    return engine.url.render_as_string(hide_password=True)


def init_db() -> None:
    """Zero-config schema bootstrap for local SQLite and tests.

    On SQLite we create any missing tables so a fresh clone runs with no setup.
    On Postgres (production) the schema is owned by Alembic migrations, so this
    is a no-op there - run `alembic upgrade head` during deploy instead.
    """
    if IS_SQLITE:
        Base.metadata.create_all(engine)


def reset_db() -> None:
    """Drop and recreate every table. Used by the demo reset and tests."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
