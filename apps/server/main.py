from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
except Exception:  # pragma: no cover - only used when requirements are missing
    PasswordHasher = None
    VerifyMismatchError = Exception

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT_DIR / "apps" / "web"
DATA_DIR = Path(os.getenv("SECURE_CHAT_DATA_DIR", ROOT_DIR / "data"))
STORE_FILE = DATA_DIR / "demo_store.json"

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ISSUER = os.getenv("JWT_ISSUER", "secure-chat-server")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "secure-chat-web")
ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TOKEN_TTL_SECONDS", "900"))
REFRESH_TTL_SECONDS = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "604800"))
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "secure_chat_refresh")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_username(username: str) -> str:
    clean = username.strip().lower()
    if not clean or len(clean) > 32:
        raise HTTPException(status_code=400, detail="Username must be 1-32 characters")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_.-")
    if any(ch not in allowed for ch in clean):
        raise HTTPException(
            status_code=400,
            detail="Username may contain letters, numbers, dot, dash and underscore",
        )
    return clean


def initial_store() -> dict[str, Any]:
    return {
        "users": {},
        "refresh_sessions": {},
        "devices": {},
        "messages": [],
        "security_events": [],
    }


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = RLock()
        self.data = initial_store()
        self.load()

    def load(self) -> None:
        with self.lock:
            if self.path.exists():
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                self.persist()

    def persist(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def reset(self) -> None:
        with self.lock:
            self.data = initial_store()
            self.persist()


store = JsonStore(STORE_FILE)

if PasswordHasher is not None:
    password_hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)
else:
    password_hasher = None


def hash_password(password: str) -> str:
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    if password_hasher is not None:
        return password_hasher.hash(password)

    # Development fallback so the server gives a clear demo path even before
    # dependencies are installed. requirements.txt installs Argon2id.
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64url_encode(salt) + "$" + base64url_encode(derived)


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("$argon2"):
        if password_hasher is None:
            raise HTTPException(status_code=500, detail="argon2-cffi is not installed")
        try:
            return password_hasher.verify(stored_hash, password)
        except VerifyMismatchError:
            return False
    if stored_hash.startswith("scrypt$"):
        _, salt_b64, digest_b64 = stored_hash.split("$", 2)
        salt = base64url_decode(salt_b64)
        expected = base64url_decode(digest_b64)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    return False


def sign_jwt(payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64url_encode(canonical_json(header).encode("utf-8"))
    payload_b64 = base64url_encode(canonical_json(payload).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{base64url_encode(signature)}"


def verify_jwt(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual = base64url_decode(signature_b64)
        if not hmac.compare_digest(expected, actual):
            raise ValueError("bad signature")
        payload = json.loads(base64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc

    now = int(time.time())
    if payload.get("iss") != JWT_ISSUER or payload.get("aud") != JWT_AUDIENCE:
        raise HTTPException(status_code=401, detail="Invalid token issuer or audience")
    if int(payload.get("exp", 0)) < now:
        raise HTTPException(status_code=401, detail="Access token expired")
    return payload


def issue_tokens(user_id: str, response: Response) -> dict[str, Any]:
    issued_at = int(time.time())
    session_id = secrets.token_urlsafe(18)
    refresh_token = secrets.token_urlsafe(36)
    access_payload = {
        "sub": user_id,
        "username": user_id,
        "session_id": session_id,
        "jti": secrets.token_urlsafe(12),
        "iat": issued_at,
        "exp": issued_at + ACCESS_TTL_SECONDS,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    refresh_hash = sha256_hex(refresh_token)
    with store.lock:
        store.data["refresh_sessions"][session_id] = {
            "id": session_id,
            "user_id": user_id,
            "refresh_token_hash": refresh_hash,
            "created_at": now_iso(),
            "expires_at": issued_at + REFRESH_TTL_SECONDS,
            "revoked_at": None,
        }
        store.persist()

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=REFRESH_TTL_SECONDS,
    )
    return {
        "access_token": sign_jwt(access_payload),
        "token_type": "bearer",
        "expires_in": ACCESS_TTL_SECONDS,
        "user": public_user(user_id),
    }


def public_user(user_id: str) -> dict[str, Any]:
    user = store.data["users"][user_id]
    return {
        "id": user["id"],
        "username": user["username"],
        "created_at": user["created_at"],
    }


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = verify_jwt(token)
    user_id = payload["sub"]
    with store.lock:
        if user_id not in store.data["users"]:
            raise HTTPException(status_code=401, detail="User no longer exists")
        return store.data["users"][user_id]


def record_event(event_type: str, actor_user_id: str | None, detail: dict[str, Any]) -> None:
    with store.lock:
        store.data["security_events"].append(
            {
                "id": "evt_" + secrets.token_urlsafe(10),
                "type": event_type,
                "actor_user_id": actor_user_id,
                "detail": detail,
                "created_at": now_iso(),
            }
        )
        store.persist()


def latest_device_for_user(user_id: str) -> dict[str, Any] | None:
    devices = [
        device
        for device in store.data["devices"].values()
        if device["user_id"] == user_id and device.get("revoked_at") is None
    ]
    if not devices:
        return None
    devices.sort(key=lambda item: item["created_at"], reverse=True)
    return devices[0]


def store_message(packet: dict[str, Any], actor_user_id: str) -> dict[str, Any]:
    if "plaintext" in canonical_json(packet).lower():
        raise HTTPException(status_code=400, detail="Plaintext must not be sent to server")

    header = packet.get("header") or {}
    sender_user_id = header.get("sender_user_id")
    recipient_user_id = header.get("recipient_user_id")
    if sender_user_id != actor_user_id:
        raise HTTPException(status_code=403, detail="Sender does not match access token")
    if recipient_user_id not in store.data["users"]:
        raise HTTPException(status_code=404, detail="Recipient does not exist")
    required = ["version", "conversation_id", "message_number"]
    if any(key not in header for key in required):
        raise HTTPException(status_code=400, detail="Encrypted packet header is incomplete")
    if "ciphertext" not in packet or "nonce" not in packet or "tag" not in packet:
        raise HTTPException(status_code=400, detail="Encrypted packet body is incomplete")

    message = {
        "id": "msg_" + secrets.token_urlsafe(12),
        "sender_user_id": sender_user_id,
        "recipient_user_id": recipient_user_id,
        "packet": packet,
        "server_received_at": now_iso(),
        "delivered_at": None,
    }
    with store.lock:
        store.data["messages"].append(message)
        store.persist()
    return message


class AuthRequest(BaseModel):
    username: str
    password: str


class DeviceRequest(BaseModel):
    device_label: str = Field(default="browser")
    public_key_jwk: dict[str, Any]
    fingerprint: str
    device_id: str | None = None


class MessageRequest(BaseModel):
    packet: dict[str, Any]


class ReplayRequest(BaseModel):
    message_id: str


class KeySubstitutionRequest(BaseModel):
    username: str


class StateCompromiseRequest(BaseModel):
    compromise_at_message: int = 3
    rekey_at_message: int = 5
    total_messages: int = 8


app = FastAPI(
    title="Secure Web Chat Course Prototype",
    description="JWT auth, public key directory, ciphertext relay, and Security Lab.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "secure-web-chat",
        "password_hasher": "argon2id" if password_hasher is not None else "scrypt-dev-fallback",
        "users": len(store.data["users"]),
        "messages": len(store.data["messages"]),
    }


@app.post("/auth/register")
def register(payload: AuthRequest, response: Response) -> dict[str, Any]:
    username = normalize_username(payload.username)
    with store.lock:
        if username in store.data["users"]:
            raise HTTPException(status_code=409, detail="Username already exists")
        store.data["users"][username] = {
            "id": username,
            "username": username,
            "password_hash": hash_password(payload.password),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        store.persist()
    record_event("USER_REGISTERED", username, {"username": username})
    return issue_tokens(username, response)


@app.post("/auth/login")
def login(payload: AuthRequest, response: Response) -> dict[str, Any]:
    username = normalize_username(payload.username)
    with store.lock:
        user = store.data["users"].get(username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    record_event("USER_LOGIN", username, {"username": username})
    return issue_tokens(username, response)


@app.post("/auth/refresh")
def refresh(response: Response, secure_chat_refresh: str | None = Cookie(default=None)) -> dict[str, Any]:
    refresh_token = secure_chat_refresh
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    token_hash = sha256_hex(refresh_token)
    now = int(time.time())
    with store.lock:
        for session in store.data["refresh_sessions"].values():
            if (
                session["refresh_token_hash"] == token_hash
                and session["revoked_at"] is None
                and session["expires_at"] > now
            ):
                return issue_tokens(session["user_id"], response)
    raise HTTPException(status_code=401, detail="Invalid refresh token")


@app.post("/auth/logout")
def logout(
    response: Response,
    user: dict[str, Any] = Depends(current_user),
    secure_chat_refresh: str | None = Cookie(default=None),
) -> dict[str, Any]:
    token_hash = sha256_hex(secure_chat_refresh or "")
    with store.lock:
        for session in store.data["refresh_sessions"].values():
            if session["user_id"] == user["id"] and session["refresh_token_hash"] == token_hash:
                session["revoked_at"] = now_iso()
        store.persist()
    response.delete_cookie(REFRESH_COOKIE_NAME)
    return {"ok": True}


@app.get("/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"user": public_user(user["id"])}


@app.get("/users")
def users(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with store.lock:
        items = [
            public_user(user_id)
            for user_id in sorted(store.data["users"])
            if user_id != user["id"]
        ]
    return {"users": items}


@app.post("/devices")
def create_or_update_device(
    payload: DeviceRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if "d" in payload.public_key_jwk:
        raise HTTPException(status_code=400, detail="Private key material is not allowed")

    device_id = payload.device_id or f"{user['id']}-browser"
    device = {
        "id": device_id,
        "user_id": user["id"],
        "device_label": payload.device_label.strip()[:80] or "browser",
        "identity_public_key": payload.public_key_jwk,
        "fingerprint": payload.fingerprint,
        "created_at": now_iso(),
        "last_seen_at": now_iso(),
        "revoked_at": None,
    }
    with store.lock:
        existing = store.data["devices"].get(device_id)
        if existing and existing["user_id"] != user["id"]:
            raise HTTPException(status_code=409, detail="Device id belongs to another user")
        if existing and existing["fingerprint"] != payload.fingerprint:
            record_event(
                "KEY_SUBSTITUTION_WARNING",
                user["id"],
                {
                    "device_id": device_id,
                    "old_fingerprint": existing["fingerprint"],
                    "new_fingerprint": payload.fingerprint,
                },
            )
            device["created_at"] = existing["created_at"]
        store.data["devices"][device_id] = device
        store.persist()
    return {"device": device}


@app.get("/devices")
def list_devices(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with store.lock:
        devices = [
            device
            for device in store.data["devices"].values()
            if device["user_id"] == user["id"] and device.get("revoked_at") is None
        ]
    return {"devices": devices}


@app.get("/keys/bundle/{username}")
def key_bundle(username: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    target = normalize_username(username)
    with store.lock:
        if target not in store.data["users"]:
            raise HTTPException(status_code=404, detail="User does not exist")
        device = latest_device_for_user(target)
    if not device:
        raise HTTPException(status_code=404, detail="User has no device key")
    return {
        "user_id": target,
        "device_id": device["id"],
        "identity_public_key": device["identity_public_key"],
        "fingerprint": device["fingerprint"],
        "created_at": device["created_at"],
    }


@app.post("/messages")
async def post_message(
    payload: MessageRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    message = store_message(payload.packet, user["id"])
    record_event(
        "CIPHERTEXT_STORED",
        user["id"],
        {"message_id": message["id"], "recipient_user_id": message["recipient_user_id"]},
    )
    await manager.send(message["recipient_user_id"], {"type": "encrypted_message", "message": message})
    return {"message": message}


@app.get("/messages/offline")
def offline_messages(
    peer: str | None = None,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    peer_id = normalize_username(peer) if peer else None
    with store.lock:
        messages = []
        for message in store.data["messages"]:
            involves_user = user["id"] in (message["sender_user_id"], message["recipient_user_id"])
            involves_peer = (
                peer_id is None
                or peer_id in (message["sender_user_id"], message["recipient_user_id"])
            )
            if involves_user and involves_peer:
                messages.append(message)
    return {"messages": messages}


@app.get("/lab/messages")
def lab_messages(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with store.lock:
        rows = []
        for message in store.data["messages"]:
            if user["id"] not in (message["sender_user_id"], message["recipient_user_id"]):
                continue
            packet = message["packet"]
            rows.append(
                {
                    "id": message["id"],
                    "sender_user_id": message["sender_user_id"],
                    "recipient_user_id": message["recipient_user_id"],
                    "message_number": packet.get("header", {}).get("message_number"),
                    "nonce": packet.get("nonce"),
                    "ciphertext": packet.get("ciphertext"),
                    "tag": packet.get("tag"),
                    "plaintext": None,
                    "plaintext_exposed": False,
                    "server_received_at": message["server_received_at"],
                }
            )
    record_event("SERVER_COMPROMISE_VIEWED", user["id"], {"visible_rows": len(rows)})
    return {"messages": rows}


@app.post("/lab/replay")
def lab_replay(payload: ReplayRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with store.lock:
        message = next((msg for msg in store.data["messages"] if msg["id"] == payload.message_id), None)
    if not message or user["id"] not in (message["sender_user_id"], message["recipient_user_id"]):
        raise HTTPException(status_code=404, detail="Message not found")
    record_event("REPLAY_PACKET_PREPARED", user["id"], {"message_id": payload.message_id})
    return {"packet": message["packet"], "expected_result": "REPLAY_REJECTED"}


@app.post("/lab/tamper")
def lab_tamper(payload: ReplayRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with store.lock:
        message = next((msg for msg in store.data["messages"] if msg["id"] == payload.message_id), None)
    if not message or user["id"] not in (message["sender_user_id"], message["recipient_user_id"]):
        raise HTTPException(status_code=404, detail="Message not found")
    packet = copy.deepcopy(message["packet"])
    ciphertext = base64url_decode(packet["ciphertext"])
    if ciphertext:
        tampered = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]
    else:
        tampered = b"x"
    packet["ciphertext"] = base64url_encode(tampered)
    record_event("TAMPER_PACKET_PREPARED", user["id"], {"message_id": payload.message_id})
    return {"packet": packet, "expected_result": "TAMPER_REJECTED"}


@app.post("/lab/key-substitution")
def lab_key_substitution(
    payload: KeySubstitutionRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    target = normalize_username(payload.username)
    if target not in store.data["users"]:
        raise HTTPException(status_code=404, detail="User does not exist")
    record_event(
        "KEY_SUBSTITUTION_WARNING",
        user["id"],
        {"target_user_id": target, "note": "Client should compare fingerprints before trusting key"},
    )
    return {
        "target_user_id": target,
        "expected_result": "KEY_SUBSTITUTION_WARNING",
        "warning": "Public key fingerprint changed. Verify safety number before sending.",
    }


@app.post("/lab/state-compromise")
def lab_state_compromise(
    payload: StateCompromiseRequest,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    compromise_at = max(payload.compromise_at_message, 1)
    total = max(payload.total_messages, compromise_at)
    rekey_at = max(payload.rekey_at_message, compromise_at + 1)
    symmetric_exposed = max(total - compromise_at, 0)
    hybrid_exposed = max(min(total, rekey_at - 1) - compromise_at, 0)
    result = {
        "compromise_at_message": compromise_at,
        "rekey_at_message": rekey_at,
        "total_messages": total,
        "symmetric_only_future_messages_exposed": symmetric_exposed,
        "hybrid_after_rekey_future_messages_exposed": hybrid_exposed,
        "recovery_point": rekey_at,
        "recovered_after_dh_ratchet": True,
    }
    record_event("DH_REKEY_RECOVERED", user["id"], result)
    return {"metrics": result}


@app.get("/lab/events")
def lab_events(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with store.lock:
        events = [
            event
            for event in store.data["security_events"]
            if event["actor_user_id"] in (None, user["id"])
        ]
    return {"events": events[-50:]}


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        self.active.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        sockets = self.active.get(user_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self.active.pop(user_id, None)

    async def send(self, user_id: str, payload: dict[str, Any]) -> None:
        sockets = list(self.active.get(user_id, set()))
        for socket in sockets:
            try:
                await socket.send_json(payload)
            except Exception:
                self.disconnect(user_id, socket)

manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    user_id: str | None = None
    try:
        first = await websocket.receive_json()
        if first.get("type") != "auth":
            await websocket.close(code=4401)
            return
        payload = verify_jwt(first.get("access_token", ""))
        user_id = payload["sub"]
        if user_id not in store.data["users"]:
            await websocket.close(code=4401)
            return
        await manager.connect(user_id, websocket)
        await websocket.send_json({"type": "auth_ok", "user_id": user_id})
        while True:
            frame = await websocket.receive_json()
            if frame.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif frame.get("type") == "encrypted_message":
                message = store_message(frame.get("packet", {}), user_id)
                await manager.send(
                    message["recipient_user_id"],
                    {"type": "encrypted_message", "message": message},
                )
    except WebSocketDisconnect:
        pass
    finally:
        if user_id:
            manager.disconnect(user_id, websocket)


def reset_demo_store() -> None:
    store.reset()


if WEB_DIR.exists():
    app.mount("/src", StaticFiles(directory=WEB_DIR / "src"), name="web-src")
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="web-assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
