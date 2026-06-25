"""One-time migration: import the legacy JSON demo store into the database.

The storage layer moved from a single JSON file to a normalised SQLAlchemy
schema. This script copies any data left in the old `data/demo_store.json` into
the configured database (SQLite locally, or Postgres via DATABASE_URL),
transforming it to the new schema as it goes:

  * ISO timestamp strings / epoch seconds  ->  native DateTime columns
  * conversation_id / message_number lifted out of the packet header into
    indexed columns, with a row created in the new `conversations` table
  * security events get a default severity and the new audit columns

Usage (from the repo root, with the venv active):

    python scripts/migrate_json_to_db.py
    python scripts/migrate_json_to_db.py --store data/demo_store.json
    python scripts/migrate_json_to_db.py --reset       # wipe DB first, then import

It is idempotent: rows whose primary key already exists are skipped, so running
it twice will not create duplicates. Use --reset to make the database mirror the
JSON file exactly (this drops current rows first).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a plain script (python scripts/migrate_json_to_db.py).
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.server.db import (  # noqa: E402
    Conversation,
    Device,
    Message,
    RefreshSession,
    SecurityEvent,
    SessionLocal,
    User,
    init_db,
    reset_db,
    safe_database_label,
)


def _to_dt(value) -> datetime | None:
    """Parse a legacy timestamp (ISO string or epoch seconds) to a datetime."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return datetime.fromisoformat(value)


def _exists(session, model, pk) -> bool:
    return pk is not None and session.get(model, pk) is not None


def migrate(store_path: Path, reset: bool) -> None:
    if not store_path.exists():
        print(f"No JSON store found at {store_path} - nothing to migrate.")
        return

    data = json.loads(store_path.read_text(encoding="utf-8"))

    if reset:
        print("Resetting database (dropping existing rows)...")
        reset_db()
    else:
        init_db()

    report: dict[str, list[int]] = {
        "users": [0, 0],
        "conversations": [0, 0],
        "devices": [0, 0],
        "refresh_sessions": [0, 0],
        "messages": [0, 0],
        "security_events": [0, 0],
    }

    def bump(table: str, inserted: bool) -> None:
        report[table][0 if inserted else 1] += 1

    with SessionLocal() as session:
        for row in data.get("users", {}).values():
            if _exists(session, User, row.get("id")):
                bump("users", False)
                continue
            session.add(
                User(
                    id=row["id"],
                    username=row["username"],
                    password_hash=row["password_hash"],
                    is_admin=bool(row.get("is_admin")),
                    created_at=_to_dt(row.get("created_at")),
                    updated_at=_to_dt(row.get("updated_at")),
                )
            )
            bump("users", True)
        session.flush()

        for row in data.get("devices", {}).values():
            if _exists(session, Device, row.get("id")):
                bump("devices", False)
                continue
            session.add(
                Device(
                    id=row["id"],
                    user_id=row["user_id"],
                    device_label=row.get("device_label", "browser"),
                    identity_public_key=row["identity_public_key"],
                    fingerprint=row["fingerprint"],
                    created_at=_to_dt(row.get("created_at")),
                    last_seen_at=_to_dt(row.get("last_seen_at")),
                    revoked_at=_to_dt(row.get("revoked_at")),
                )
            )
            bump("devices", True)

        for row in data.get("refresh_sessions", {}).values():
            if _exists(session, RefreshSession, row.get("id")):
                bump("refresh_sessions", False)
                continue
            session.add(
                RefreshSession(
                    id=row["id"],
                    user_id=row["user_id"],
                    refresh_token_hash=row["refresh_token_hash"],
                    created_at=_to_dt(row.get("created_at")),
                    expires_at=_to_dt(row.get("expires_at")),
                    revoked_at=_to_dt(row.get("revoked_at")),
                )
            )
            bump("refresh_sessions", True)

        for row in data.get("messages", []):
            if _exists(session, Message, row.get("id")):
                bump("messages", False)
                continue
            header = (row.get("packet") or {}).get("header", {})
            conversation_id = header.get("conversation_id")
            sender = row["sender_user_id"]
            recipient = row["recipient_user_id"]
            if conversation_id and session.get(Conversation, conversation_id) is None:
                a, b = sorted([sender, recipient])
                session.add(
                    Conversation(
                        id=conversation_id,
                        participant_a=a,
                        participant_b=b,
                        created_at=_to_dt(row.get("server_received_at")),
                        last_message_at=_to_dt(row.get("server_received_at")),
                    )
                )
                bump("conversations", True)
            session.add(
                Message(
                    id=row["id"],
                    conversation_id=conversation_id,
                    sender_user_id=sender,
                    recipient_user_id=recipient,
                    message_number=int(header.get("message_number", 0)),
                    packet=row["packet"],
                    server_received_at=_to_dt(row.get("server_received_at")),
                    delivered_at=_to_dt(row.get("delivered_at")),
                )
            )
            bump("messages", True)

        for row in data.get("security_events", []):
            if _exists(session, SecurityEvent, row.get("id")):
                bump("security_events", False)
                continue
            session.add(
                SecurityEvent(
                    id=row["id"],
                    type=row["type"],
                    severity=row.get("severity", "info"),
                    actor_user_id=row.get("actor_user_id"),
                    actor_ip=row.get("actor_ip"),
                    actor_user_agent=row.get("actor_user_agent"),
                    detail=row.get("detail", {}),
                    created_at=_to_dt(row.get("created_at")),
                )
            )
            bump("security_events", True)

        session.commit()

    print(f"Target database: {safe_database_label()}")
    print(f"Source JSON:     {store_path}")
    for table, (inserted, skipped) in report.items():
        print(f"  {table:<18} inserted={inserted} skipped={skipped}")
    print("Migration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy JSON store into the database.")
    parser.add_argument(
        "--store",
        default=str(ROOT_DIR / "data" / "demo_store.json"),
        help="Path to the legacy JSON store (default: data/demo_store.json).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all DB rows before importing so the DB mirrors the JSON file.",
    )
    args = parser.parse_args()
    migrate(Path(args.store), args.reset)


if __name__ == "__main__":
    main()
