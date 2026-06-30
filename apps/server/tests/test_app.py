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

# ----- Identity keys, signatures, and pre-keys -----

def sample_signing_key(username: str) -> dict[str, str]:
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": f"{username}_sign_x",
        "y": f"{username}_sign_y",
        "ext": "true",
    }


def test_upload_signing_key() -> None:
    client = TestClient(app)
    alice_token = register(client, "alice")
    signing_key = sample_signing_key("alice")
    response = client.post(
        "/keys/signing-key",
        headers=auth_headers(alice_token),
        json={"signing_key_jwk": signing_key, "fingerprint": "alice-sign-fp"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True


def test_pre_key_upload_and_bundle_includes_pre_keys() -> None:
    client = TestClient(app)
    alice_token = register(client, "alice")
    bob_token = register(client, "bob")

    # Alice uploads device + signing key + pre-keys
    client.post(
        "/devices",
        headers=auth_headers(alice_token),
        json={
            "device_id": "alice-browser",
            "device_label": "Browser",
            "public_key_jwk": sample_public_key("alice"),
            "fingerprint": "alice-fingerprint",
            "device_signature": "alice-sig-over-device-key",
        },
    )
    client.post(
        "/keys/signing-key",
        headers=auth_headers(alice_token),
        json={"signing_key_jwk": sample_signing_key("alice"), "fingerprint": "alice-sign-fp"},
    )
    client.post(
        "/keys/pre-keys",
        headers=auth_headers(alice_token),
        json={
            "pre_keys": [
                {
                    "key_id": "spk1",
                    "device_id": "alice-browser",
                    "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "spk_x", "y": "spk_y"},
                    "fingerprint": "alice-spk-fp",
                    "signature": "alice-sig-over-spk",
                    "is_otp": False,
                },
                {
                    "key_id": "otp1",
                    "device_id": "alice-browser",
                    "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "otp_x", "y": "otp_y"},
                    "fingerprint": "alice-otp1-fp",
                    "signature": "alice-sig-over-otp1",
                    "is_otp": True,
                },
            ]
        },
    )

    # Bob now fetches Alice's bundle — should see all the new fields
    bundle = client.get("/keys/bundle/alice", headers=auth_headers(bob_token))
    assert bundle.status_code == 200, bundle.text
    data = bundle.json()

    # Identity (signing) key should be present
    assert data["signing_public_key"] is not None
    assert data["signing_public_key"]["x"] == "alice_sign_x"

    # Device signature should be present
    assert data["device_signature"] == "alice-sig-over-device-key"

    # Signed pre-key should be present
    assert data["signed_pre_key"] is not None
    assert data["signed_pre_key"]["fingerprint"] == "alice-spk-fp"

    # One-time pre-key should be present
    assert data["one_time_pre_key"] is not None
    assert data["one_time_pre_key"]["fingerprint"] == "alice-otp1-fp"


def test_pre_keys_endpoint() -> None:
    client = TestClient(app)
    alice_token = register(client, "alice")

    client.post(
        "/devices",
        headers=auth_headers(alice_token),
        json={
            "device_id": "alice-browser",
            "device_label": "Browser",
            "public_key_jwk": sample_public_key("alice"),
            "fingerprint": "alice-fingerprint",
        },
    )

    # Upload pre-keys
    client.post(
        "/keys/pre-keys",
        headers=auth_headers(alice_token),
        json={
            "pre_keys": [
                {
                    "key_id": "spk1",
                    "device_id": "alice-browser",
                    "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "spk_x", "y": "spk_y"},
                    "fingerprint": "alice-spk-fp",
                    "signature": "alice-sig-over-spk",
                    "is_otp": False,
                },
                {
                    "key_id": "otp1",
                    "device_id": "alice-browser",
                    "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "otp_x", "y": "otp_y"},
                    "fingerprint": "alice-otp1-fp",
                    "signature": "alice-sig-over-otp1",
                    "is_otp": True,
                },
            ]
        },
    )

    # Fetch pre-keys for alice
    response = client.get("/keys/pre-keys/alice", headers=auth_headers(alice_token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["one_time_pre_keys"]) == 1
    assert data["one_time_pre_keys"][0]["fingerprint"] == "alice-otp1-fp"
    assert len(data["signed_pre_keys"]) == 1
    assert data["signed_pre_keys"][0]["fingerprint"] == "alice-spk-fp"


def test_consume_one_time_pre_key() -> None:
    client = TestClient(app)
    alice_token = register(client, "alice")
    bob_token = register(client, "bob")

    client.post(
        "/devices",
        headers=auth_headers(alice_token),
        json={
            "device_id": "alice-browser",
            "device_label": "Browser",
            "public_key_jwk": sample_public_key("alice"),
            "fingerprint": "alice-fingerprint",
        },
    )
    client.post(
        "/keys/pre-keys",
        headers=auth_headers(alice_token),
        json={
            "pre_keys": [
                {
                    "key_id": "otp1",
                    "device_id": "alice-browser",
                    "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "otp_x", "y": "otp_y"},
                    "fingerprint": "alice-otp1-fp",
                    "signature": "alice-sig-over-otp1",
                    "is_otp": True,
                },
            ]
        },
    )

    # Bob consumes Alice's OTP
    consumed = client.post("/keys/consume-otp/alice", headers=auth_headers(bob_token))
    assert consumed.status_code == 200, consumed.text
    assert consumed.json()["pre_key"] is not None

    # Second consume should return None (already consumed)
    second = client.post("/keys/consume-otp/alice", headers=auth_headers(bob_token))
    assert second.status_code == 200, second.text
    assert second.json()["pre_key"] is None


def test_bundle_includes_signature_and_device_signature() -> None:
    client = TestClient(app)
    alice_token = register(client, "alice")
    bob_token = register(client, "bob")

    # Bob uploads device with signature and signing key
    client.post(
        "/devices",
        headers=auth_headers(bob_token),
        json={
            "device_id": "bob-browser",
            "device_label": "Browser",
            "public_key_jwk": sample_public_key("bob"),
            "fingerprint": "bob-fingerprint",
            "device_signature": "bob-ik-sig-over-device",
        },
    )
    client.post(
        "/keys/signing-key",
        headers=auth_headers(bob_token),
        json={"signing_key_jwk": sample_signing_key("bob"), "fingerprint": "bob-sign-fp"},
    )
    client.post(
        "/keys/pre-keys",
        headers=auth_headers(bob_token),
        json={
            "pre_keys": [
                {
                    "key_id": "spk1",
                    "device_id": "bob-browser",
                    "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "spk_x", "y": "spk_y"},
                    "fingerprint": "bob-spk-fp",
                    "signature": "bob-ik-sig-over-spk",
                    "is_otp": False,
                },
            ]
        },
    )

    bundle = client.get("/keys/bundle/bob", headers=auth_headers(alice_token))
    assert bundle.status_code == 200, bundle.text
    data = bundle.json()
    assert data["signing_public_key"] is not None
    assert data["device_signature"] == "bob-ik-sig-over-device"
    assert data["signed_pre_key"] is not None
    assert data["signed_pre_key"]["signature"] == "bob-ik-sig-over-spk"
    assert data["fingerprint"] == "bob-fingerprint"
