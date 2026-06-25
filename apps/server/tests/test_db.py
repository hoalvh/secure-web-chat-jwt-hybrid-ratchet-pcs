"""Database-level tests for the redesigned schema.

These cover what the storage rewrite added on top of the API behaviour:
referential integrity (foreign keys), cascade deletes, conversation
normalisation, and expired-session cleanup.
"""

import sqlalchemy.exc
from fastapi.testclient import TestClient

from apps.server.db import (
    Conversation,
    Device,
    Message,
    RefreshSession,
    SessionLocal,
    User,
    utcnow,
)
from apps.server.main import app, cleanup_expired_sessions, reset_demo_store
from datetime import timedelta


def setup_function() -> None:
    reset_demo_store()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, username: str) -> str:
    response = client.post("/auth/register", json={"username": username, "password": "pass1234"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def send_message(client: TestClient, token: str, sender: str, recipient: str, number: int = 1):
    packet = {
        "version": 1,
        "algorithm": "ECDH-P-256+HKDF-SHA256+AES-GCM",
        "header": {
            "version": 1,
            "conversation_id": "__".join(sorted([sender, recipient])),
            "sender_user_id": sender,
            "recipient_user_id": recipient,
            "message_number": number,
        },
        "nonce": "nonce",
        "ciphertext": "ciphertext",
        "tag": "tag",
    }
    return client.post("/messages", headers=auth_headers(token), json={"packet": packet})


def test_foreign_key_rejects_orphan_message() -> None:
    """A message referencing non-existent users/conversation must be rejected."""
    with SessionLocal() as session:
        session.add(
            Message(
                id="msg_orphan",
                conversation_id="ghost",
                sender_user_id="nobody-a",
                recipient_user_id="nobody-b",
                message_number=1,
                packet={"ciphertext": "x"},
                server_received_at=utcnow(),
            )
        )
        try:
            session.commit()
            raise AssertionError("orphan message was accepted - foreign keys not enforced")
        except sqlalchemy.exc.IntegrityError:
            pass


def test_sending_message_normalises_conversation() -> None:
    client = TestClient(app)
    alice = register(client, "alice")
    register(client, "bob")

    assert send_message(client, alice, "alice", "bob").status_code == 200

    with SessionLocal() as session:
        conversations = session.query(Conversation).all()
        assert len(conversations) == 1
        conv = conversations[0]
        assert conv.id == "alice__bob"
        assert {conv.participant_a, conv.participant_b} == {"alice", "bob"}
        assert conv.last_message_at is not None

        message = session.query(Message).one()
        assert message.conversation_id == "alice__bob"
        assert message.message_number == 1


def test_deleting_user_cascades_to_their_data() -> None:
    client = TestClient(app)
    alice = register(client, "alice")
    register(client, "bob")
    client.post(
        "/devices",
        headers=auth_headers(alice),
        json={
            "device_id": "alice-browser",
            "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "ax", "y": "ay"},
            "fingerprint": "fp-alice",
        },
    )
    assert send_message(client, alice, "alice", "bob").status_code == 200

    with SessionLocal() as session:
        alice_row = session.get(User, "alice")
        session.delete(alice_row)
        session.commit()

    with SessionLocal() as session:
        assert session.get(User, "alice") is None
        assert session.query(Device).filter_by(user_id="alice").count() == 0
        assert session.query(RefreshSession).filter_by(user_id="alice").count() == 0
        # message + conversation cascade away with the participant
        assert session.query(Message).count() == 0
        assert session.query(Conversation).count() == 0


def test_expired_sessions_are_cleaned_up() -> None:
    register(TestClient(app), "alice")
    with SessionLocal() as session:
        session.add(
            RefreshSession(
                id="expired-session",
                user_id="alice",
                refresh_token_hash="deadbeef",
                created_at=utcnow() - timedelta(days=30),
                expires_at=utcnow() - timedelta(days=1),
                revoked_at=None,
            )
        )
        session.commit()

    cleanup_expired_sessions()

    with SessionLocal() as session:
        assert session.get(RefreshSession, "expired-session") is None
        # the live session created during register must survive
        assert session.query(RefreshSession).filter_by(user_id="alice").count() >= 1


def test_security_events_capture_severity_and_ip() -> None:
    client = TestClient(app)
    admin = register(client, "admin")
    alice = register(client, "alice")

    # A warning-level event with a different actor.
    client.post("/lab/key-substitution", headers=auth_headers(alice), json={"username": "admin"})

    dashboard = client.get("/admin/dashboard", headers=auth_headers(admin)).json()
    events = dashboard["security_events"]
    assert events, "expected security events"
    # Every event row now carries severity and the new audit fields.
    assert all("severity" in e and "actor_ip" in e and "actor_user_agent" in e for e in events)
    warning = next(e for e in events if e["type"] == "KEY_SUBSTITUTION_WARNING")
    assert warning["severity"] == "warning"
    assert warning["actor_user_id"] == "alice"
