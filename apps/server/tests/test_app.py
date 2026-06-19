from fastapi.testclient import TestClient

from apps.server.main import app, reset_demo_store


def setup_function() -> None:
    reset_demo_store()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, username: str) -> str:
    response = client.post(
        "/auth/register",
        json={"username": username, "password": "pass1234"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def sample_public_key(username: str) -> dict[str, str]:
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": f"{username}_public_x",
        "y": f"{username}_public_y",
        "ext": "true",
    }


def test_register_login_device_and_ciphertext_lab_flow() -> None:
    client = TestClient(app)
    alice_token = register(client, "alice")
    bob_token = register(client, "bob")

    device_response = client.post(
        "/devices",
        headers=auth_headers(alice_token),
        json={
            "device_id": "alice-browser",
            "device_label": "Browser",
            "public_key_jwk": sample_public_key("alice"),
            "fingerprint": "alice-fingerprint",
        },
    )
    assert device_response.status_code == 200, device_response.text
    assert "d" not in device_response.json()["device"]["identity_public_key"]

    client.post(
        "/devices",
        headers=auth_headers(bob_token),
        json={
            "device_id": "bob-browser",
            "device_label": "Browser",
            "public_key_jwk": sample_public_key("bob"),
            "fingerprint": "bob-fingerprint",
        },
    )

    bundle = client.get("/keys/bundle/bob", headers=auth_headers(alice_token))
    assert bundle.status_code == 200, bundle.text
    assert bundle.json()["fingerprint"] == "bob-fingerprint"

    packet = {
        "version": 1,
        "algorithm": "ECDH-P-256+HKDF-SHA256+AES-GCM",
        "header": {
            "version": 1,
            "conversation_id": "alice__bob",
            "sender_user_id": "alice",
            "sender_device_id": "alice-browser",
            "recipient_user_id": "bob",
            "recipient_device_id": "bob-browser",
            "message_number": 1,
            "ratchet_public_key": "alice-fingerprint",
        },
        "nonce": "nonce",
        "ciphertext": "ciphertext",
        "tag": "tag",
    }
    message_response = client.post(
        "/messages",
        headers=auth_headers(alice_token),
        json={"packet": packet},
    )
    assert message_response.status_code == 200, message_response.text

    lab_response = client.get("/lab/messages", headers=auth_headers(bob_token))
    assert lab_response.status_code == 200, lab_response.text
    lab_row = lab_response.json()["messages"][0]
    assert lab_row["plaintext"] is None
    assert lab_row["plaintext_exposed"] is False
    assert lab_row["ciphertext"] == "ciphertext"


def test_server_rejects_plaintext_in_message_packet() -> None:
    client = TestClient(app)
    token = register(client, "alice")
    register(client, "bob")
    response = client.post(
        "/messages",
        headers=auth_headers(token),
        json={
            "packet": {
                "header": {
                    "version": 1,
                    "conversation_id": "alice__bob",
                    "sender_user_id": "alice",
                    "recipient_user_id": "bob",
                    "message_number": 1,
                },
                "nonce": "nonce",
                "ciphertext": "ciphertext",
                "tag": "tag",
                "plaintext": "hello bob",
            }
        },
    )
    assert response.status_code == 400


def test_admin_dashboard_exposes_server_side_demo_records_to_admin_only() -> None:
    client = TestClient(app)
    admin_token = register(client, "admin")
    alice_token = register(client, "alice")
    register(client, "bob")

    packet = {
        "version": 1,
        "algorithm": "ECDH-P-256+HKDF-SHA256+AES-GCM",
        "header": {
            "version": 1,
            "conversation_id": "alice__bob",
            "sender_user_id": "alice",
            "recipient_user_id": "bob",
            "message_number": 1,
        },
        "nonce": "nonce",
        "ciphertext": "ciphertext",
        "tag": "tag",
    }
    message_response = client.post(
        "/messages",
        headers=auth_headers(alice_token),
        json={"packet": packet},
    )
    assert message_response.status_code == 200, message_response.text

    forbidden = client.get("/admin/dashboard", headers=auth_headers(alice_token))
    assert forbidden.status_code == 403

    dashboard = client.get("/admin/dashboard", headers=auth_headers(admin_token))
    assert dashboard.status_code == 200, dashboard.text
    data = dashboard.json()
    alice = next(user for user in data["users"] if user["username"] == "alice")
    assert alice["is_admin"] is False
    assert alice["password_hash"]
    assert "pass1234" not in alice["password_hash"]
    admin = next(user for user in data["users"] if user["username"] == "admin")
    assert admin["is_admin"] is True
    assert data["messages"][0]["ciphertext"] == "ciphertext"
    assert data["messages"][0]["plaintext"] is None


def test_normal_user_contact_list_hides_admin_accounts() -> None:
    client = TestClient(app)
    register(client, "admin")
    alice_token = register(client, "alice")
    register(client, "bob")

    response = client.get("/users", headers=auth_headers(alice_token))
    assert response.status_code == 200, response.text
    usernames = [user["username"] for user in response.json()["users"]]
    assert usernames == ["bob"]
