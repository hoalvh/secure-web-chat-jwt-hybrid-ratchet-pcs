from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import timedelta
from pathlib import Path
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
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from apps.server.db import (
    Conversation,
    DATABASE_URL,
    Device,
    Message,
    PreKey,
    RefreshSession,
    SecurityEvent,
    SessionLocal,
    User,
    init_db,
    reset_db,
    safe_database_label,
    utcnow,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT_DIR / "apps" / "web"

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ISSUER = os.getenv("JWT_ISSUER", "secure-chat-server")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "secure-chat-web")
ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TOKEN_TTL_SECONDS", "900"))
REFRESH_TTL_SECONDS = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "604800"))
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "secure_chat_refresh")
# Refresh/session cookies must be Secure in production (HTTPS). Keep it off for
# the local HTTP demo and flip it on with COOKIE_SECURE=true behind TLS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
# Extra browser origins allowed for CORS, comma separated (e.g. your domain).
EXTRA_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
ADMIN_USERNAMES = {
    username.strip().lower()
    for username in os.getenv("ADMIN_USERNAMES", "admin").split(",")
    if username.strip()
}


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


def username_is_admin(user_id: str) -> bool:
    return user_id.strip().lower() in ADMIN_USERNAMES


def user_is_admin(user: dict[str, Any]) -> bool:
    return bool(user.get("is_admin")) or username_is_admin(user["id"])


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    # Honour the first X-Forwarded-For hop when running behind a reverse proxy.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


def client_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    agent = request.headers.get("user-agent")
    return agent[:256] if agent else None


init_db()

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


def cleanup_expired_sessions() -> None:
    """Delete refresh sessions whose absolute lifetime has passed."""
    with SessionLocal() as session:
        session.execute(delete(RefreshSession).where(RefreshSession.expires_at < utcnow()))
        session.commit()


def issue_tokens(user_id: str, response: Response) -> dict[str, Any]:
    issued_epoch = int(time.time())
    issued_at = utcnow()
    session_id = secrets.token_urlsafe(18)
    refresh_token = secrets.token_urlsafe(36)
    access_payload = {
        "sub": user_id,
        "username": user_id,
        "session_id": session_id,
        "jti": secrets.token_urlsafe(12),
        "iat": issued_epoch,
        "exp": issued_epoch + ACCESS_TTL_SECONDS,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    refresh_hash = sha256_hex(refresh_token)
    with SessionLocal() as session:
        session.add(
            RefreshSession(
                id=session_id,
                user_id=user_id,
                refresh_token_hash=refresh_hash,
                created_at=issued_at,
                expires_at=issued_at + timedelta(seconds=REFRESH_TTL_SECONDS),
                revoked_at=None,
            )
        )
        session.commit()

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
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
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id": user.id,
            "username": user.username,
            "is_admin": user_is_admin(user.as_dict()),
            "created_at": user.as_dict()["created_at"],
        }


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = verify_jwt(token)
    user_id = payload["sub"]
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="User no longer exists")
        return user.as_dict()


def require_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not user_is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def record_event(
    event_type: str,
    actor_user_id: str | None,
    detail: dict[str, Any],
    severity: str = "info",
    request: Request | None = None,
) -> None:
    with SessionLocal() as session:
        session.add(
            SecurityEvent(
                id="evt_" + secrets.token_urlsafe(10),
                type=event_type,
                severity=severity,
                actor_user_id=actor_user_id,
                actor_ip=client_ip(request),
                actor_user_agent=client_user_agent(request),
                detail=detail,
                created_at=utcnow(),
            )
        )
        session.commit()


def latest_device_for_user(session, user_id: str) -> Device | None:
    stmt = (
        select(Device)
        .where(Device.user_id == user_id, Device.revoked_at.is_(None))
        .order_by(Device.created_at.desc())
    )
    return session.scalars(stmt).first()


def ensure_conversation(session, conversation_id: str, sender: str, recipient: str) -> None:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        participant_a, participant_b = sorted([sender, recipient])
        session.add(
            Conversation(
                id=conversation_id,
                participant_a=participant_a,
                participant_b=participant_b,
                created_at=utcnow(),
                last_message_at=utcnow(),
            )
        )
    else:
        conversation.last_message_at = utcnow()


def store_message(packet: dict[str, Any], actor_user_id: str) -> dict[str, Any]:
    if "plaintext" in canonical_json(packet).lower():
        raise HTTPException(status_code=400, detail="Plaintext must not be sent to server")

    header = packet.get("header") or {}
    sender_user_id = header.get("sender_user_id")
    recipient_user_id = header.get("recipient_user_id")
    if sender_user_id != actor_user_id:
        raise HTTPException(status_code=403, detail="Sender does not match access token")
    required = ["version", "conversation_id", "message_number"]
    if any(key not in header for key in required):
        raise HTTPException(status_code=400, detail="Encrypted packet header is incomplete")
    if "ciphertext" not in packet or "nonce" not in packet or "tag" not in packet:
        raise HTTPException(status_code=400, detail="Encrypted packet body is incomplete")

    try:
        message_number = int(header["message_number"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="message_number must be an integer") from exc

    conversation_id = header["conversation_id"]
    with SessionLocal() as session:
        if session.get(User, recipient_user_id) is None:
            raise HTTPException(status_code=404, detail="Recipient does not exist")
        ensure_conversation(session, conversation_id, sender_user_id, recipient_user_id)
        message = Message(
            id="msg_" + secrets.token_urlsafe(12),
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
            message_number=message_number,
            packet=packet,
            server_received_at=utcnow(),
            delivered_at=None,
        )
        session.add(message)
        session.commit()
        return message.as_dict()


class AuthRequest(BaseModel):
    username: str
    password: str


class DeviceRequest(BaseModel):
    device_label: str = Field(default="browser")
    public_key_jwk: dict[str, Any]
    fingerprint: str
    device_signature: str | None = None
    device_id: str | None = None


class MessageRequest(BaseModel):
    packet: dict[str, Any]


class SigningKeyRequest(BaseModel):
    signing_key_jwk: dict[str, Any]
    fingerprint: str


class PreKeyUploadRequest(BaseModel):
    pre_keys: list[dict[str, Any]]


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
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", *EXTRA_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    with SessionLocal() as session:
        user_count = session.scalar(select(func.count()).select_from(User)) or 0
        message_count = session.scalar(select(func.count()).select_from(Message)) or 0
    return {
        "ok": True,
        "service": "secure-web-chat",
        "password_hasher": "argon2id" if password_hasher is not None else "scrypt-dev-fallback",
        "database": "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql",
        "users": user_count,
        "messages": message_count,
    }


@app.post("/auth/register")
def register(payload: AuthRequest, request: Request, response: Response) -> dict[str, Any]:
    username = normalize_username(payload.username)
    with SessionLocal() as session:
        if session.get(User, username) is not None:
            raise HTTPException(status_code=409, detail="Username already exists")
        now = utcnow()
        session.add(
            User(
                id=username,
                username=username,
                password_hash=hash_password(payload.password),
                is_admin=username_is_admin(username),
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    record_event("USER_REGISTERED", username, {"username": username}, request=request)
    return issue_tokens(username, response)


@app.post("/auth/login")
def login(payload: AuthRequest, request: Request, response: Response) -> dict[str, Any]:
    username = normalize_username(payload.username)
    with SessionLocal() as session:
        user = session.get(User, username)
        stored_hash = user.password_hash if user else None
    if not stored_hash or not verify_password(payload.password, stored_hash):
        record_event(
            "LOGIN_FAILED", None, {"username": username}, severity="warning", request=request
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")
    cleanup_expired_sessions()
    record_event("USER_LOGIN", username, {"username": username}, request=request)
    return issue_tokens(username, response)


@app.post("/auth/refresh")
def refresh(response: Response, secure_chat_refresh: str | None = Cookie(default=None)) -> dict[str, Any]:
    refresh_token = secure_chat_refresh
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    token_hash = sha256_hex(refresh_token)
    with SessionLocal() as session:
        stmt = select(RefreshSession).where(
            RefreshSession.refresh_token_hash == token_hash,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > utcnow(),
        )
        match = session.scalars(stmt).first()
        user_id = match.user_id if match else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    cleanup_expired_sessions()
    return issue_tokens(user_id, response)


@app.post("/auth/logout")
def logout(
    response: Response,
    user: dict[str, Any] = Depends(current_user),
    secure_chat_refresh: str | None = Cookie(default=None),
) -> dict[str, Any]:
    token_hash = sha256_hex(secure_chat_refresh or "")
    with SessionLocal() as session:
        stmt = select(RefreshSession).where(
            RefreshSession.user_id == user["id"],
            RefreshSession.refresh_token_hash == token_hash,
        )
        for match in session.scalars(stmt):
            match.revoked_at = utcnow()
        session.commit()
    response.delete_cookie(REFRESH_COOKIE_NAME)
    return {"ok": True}


@app.get("/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"user": public_user(user["id"])}


@app.post("/keys/signing-key")
def upload_signing_key(
    payload: SigningKeyRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    with SessionLocal() as session:
        db_user = session.get(User, user["id"])
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        db_user.signing_public_key = payload.signing_key_jwk
        db_user.updated_at = utcnow()
        session.commit()
    record_event("SIGNING_KEY_UPLOADED", user["id"], {"fingerprint": payload.fingerprint}, request=request)
    return {"ok": True, "fingerprint": payload.fingerprint}


@app.get("/users")
def users(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    current_is_admin = user_is_admin(user)
    with SessionLocal() as session:
        rows = session.scalars(select(User).order_by(User.id)).all()
        items = [
            {
                "id": row.id,
                "username": row.username,
                "is_admin": user_is_admin(row.as_dict()),
                "created_at": row.as_dict()["created_at"],
            }
            for row in rows
            if row.id != user["id"]
            and (current_is_admin or not user_is_admin(row.as_dict()))
        ]
    return {"users": items}


@app.get("/admin/dashboard")
def admin_dashboard(request: Request, admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with SessionLocal() as session:
        users = [
            {
                "id": item.id,
                "username": item.username,
                "is_admin": user_is_admin(item.as_dict()),
                "password_hash": item.password_hash,
                "created_at": item.as_dict()["created_at"],
                "updated_at": item.as_dict()["updated_at"],
            }
            for item in session.scalars(select(User).order_by(User.username)).all()
        ]
        devices = [item.as_dict() for item in session.scalars(select(Device).order_by(Device.id)).all()]
        messages = []
        for item in session.scalars(select(Message).order_by(Message.seq)).all():
            packet = item.packet
            messages.append(
                {
                    "id": item.id,
                    "sender_user_id": item.sender_user_id,
                    "recipient_user_id": item.recipient_user_id,
                    "conversation_id": item.conversation_id,
                    "message_number": item.message_number,
                    "algorithm": packet.get("algorithm"),
                    "nonce": packet.get("nonce"),
                    "ciphertext": packet.get("ciphertext"),
                    "tag": packet.get("tag"),
                    "packet": packet,
                    "plaintext": None,
                    "plaintext_exposed": False,
                    "server_received_at": item.as_dict()["server_received_at"],
                    "delivered_at": item.as_dict()["delivered_at"],
                }
            )
        refresh_sessions = [
            item.as_dict()
            for item in session.scalars(
                select(RefreshSession).order_by(RefreshSession.created_at)
            ).all()
        ]
        conversations = [
            item.as_dict()
            for item in session.scalars(
                select(Conversation).order_by(Conversation.created_at)
            ).all()
        ]
        event_rows = session.scalars(select(SecurityEvent).order_by(SecurityEvent.seq)).all()
        events = [item.as_dict() for item in event_rows][-100:]

    record_event(
        "ADMIN_DASHBOARD_VIEWED",
        admin["id"],
        {"visible_users": len(users), "visible_messages": len(messages)},
        request=request,
    )
    return {
        "admin": public_user(admin["id"]),
        "storage": {
            "store_file": safe_database_label(),
            "users": len(users),
            "devices": len(devices),
            "conversations": len(conversations),
            "messages": len(messages),
            "refresh_sessions": len(refresh_sessions),
            "security_events": len(events),
        },
        "users": users,
        "devices": devices,
        "conversations": conversations,
        "messages": messages,
        "refresh_sessions": refresh_sessions,
        "security_events": events,
    }


@app.post("/devices")
def create_or_update_device(
    payload: DeviceRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if "d" in payload.public_key_jwk:
        raise HTTPException(status_code=400, detail="Private key material is not allowed")

    device_id = payload.device_id or f"{user['id']}-browser"
    with SessionLocal() as session:
        existing = session.get(Device, device_id)
        if existing and existing.user_id != user["id"]:
            raise HTTPException(status_code=409, detail="Device id belongs to another user")

        created_at = utcnow()
        substitution = None
        if existing:
            created_at = existing.created_at
            if existing.fingerprint != payload.fingerprint:
                substitution = {
                    "device_id": device_id,
                    "old_fingerprint": existing.fingerprint,
                    "new_fingerprint": payload.fingerprint,
                }
            device = existing
        else:
            device = Device(id=device_id)
            session.add(device)

        device.user_id = user["id"]
        device.device_label = payload.device_label.strip()[:80] or "browser"
        device.identity_public_key = payload.public_key_jwk
        device.fingerprint = payload.fingerprint
        device.device_signature = payload.device_signature
        device.created_at = created_at
        device.last_seen_at = utcnow()
        device.revoked_at = None
        session.commit()
        result = device.as_dict()

    if substitution is not None:
        record_event(
            "KEY_SUBSTITUTION_WARNING", user["id"], substitution, severity="warning", request=request
        )
    return {"device": result}


@app.get("/devices")
def list_devices(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        stmt = select(Device).where(
            Device.user_id == user["id"], Device.revoked_at.is_(None)
        )
        devices = [device.as_dict() for device in session.scalars(stmt).all()]
    return {"devices": devices}


@app.get("/keys/bundle/{username}")
def key_bundle(username: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    target = normalize_username(username)
    with SessionLocal() as session:
        target_user = session.get(User, target)
        if target_user is None:
            raise HTTPException(status_code=404, detail="User does not exist")
        device = latest_device_for_user(session, target)
        if not device:
            raise HTTPException(status_code=404, detail="User has no device key")

        # Fetch an available one-time pre-key
        otp_stmt = (
            select(PreKey)
            .where(
                PreKey.user_id == target,
                PreKey.is_otp == True,
                PreKey.consumed_at.is_(None),
            )
            .order_by(PreKey.created_at.asc())
            .limit(1)
        )
        one_time_pre_key = session.scalars(otp_stmt).first()

        # Fetch signed pre-key (non-OTP)
        spk_stmt = (
            select(PreKey)
            .where(
                PreKey.user_id == target,
                PreKey.is_otp == False,
                PreKey.consumed_at.is_(None),
            )
            .order_by(PreKey.created_at.desc())
            .limit(1)
        )
        signed_pre_key = session.scalars(spk_stmt).first()

        bundle = {
            "user_id": target,
            "device_id": device.id,
            "identity_public_key": device.identity_public_key,
            "fingerprint": device.fingerprint,
            "device_signature": device.device_signature,
            "signing_public_key": target_user.signing_public_key,
            "signed_pre_key": signed_pre_key.as_dict() if signed_pre_key else None,
            "one_time_pre_key": one_time_pre_key.as_dict() if one_time_pre_key else None,
            "created_at": device.as_dict()["created_at"],
        }
    return bundle


@app.post("/keys/pre-keys")
def upload_pre_keys(
    payload: PreKeyUploadRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    now = utcnow()
    created = 0
    with SessionLocal() as session:
        for key_data in payload.pre_keys:
            if "private_key_jwk" in key_data or (key_data.get("public_key_jwk") and "d" in key_data["public_key_jwk"]):
                record_event("PRIVATE_KEY_REJECTED", user["id"], {"note": "Attempted to upload private key material"}, severity="warning", request=request)
                raise HTTPException(status_code=400, detail="Private key material is not allowed")
            pre_key_id = f"pk_{user['id']}_{key_data.get('key_id', key_data.get('fingerprint', secrets.token_urlsafe(8)))}"
            existing = session.get(PreKey, pre_key_id)
            if existing:
                continue
            session.add(
                PreKey(
                    id=pre_key_id,
                    user_id=user["id"],
                    device_id=key_data.get("device_id", f"{user['id']}-browser"),
                    key_id=key_data.get("key_id", secrets.token_urlsafe(8)),
                    public_key_jwk=key_data["public_key_jwk"],
                    fingerprint=key_data["fingerprint"],
                    signature=key_data.get("signature", ""),
                    is_otp=key_data.get("is_otp", False),
                    consumed_at=None,
                    created_at=now,
                )
            )
            created += 1
        session.commit()
    record_event("PRE_KEYS_UPLOADED", user["id"], {"count": created}, request=request)
    return {"ok": True, "created": created}


@app.get("/keys/pre-keys/{username}")
def get_pre_keys(username: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    target = normalize_username(username)
    with SessionLocal() as session:
        otp_stmt = (
            select(PreKey)
            .where(
                PreKey.user_id == target,
                PreKey.is_otp == True,
                PreKey.consumed_at.is_(None),
            )
            .order_by(PreKey.created_at.asc())
        )
        one_time_keys = [k.as_dict() for k in session.scalars(otp_stmt).all()]

        spk_stmt = (
            select(PreKey)
            .where(
                PreKey.user_id == target,
                PreKey.is_otp == False,
                PreKey.consumed_at.is_(None),
            )
            .order_by(PreKey.created_at.desc())
        )
        signed_pre_keys = [k.as_dict() for k in session.scalars(spk_stmt).all()]
    return {"one_time_pre_keys": one_time_keys, "signed_pre_keys": signed_pre_keys}


@app.post("/keys/consume-otp/{username}")
def consume_one_time_pre_key(
    username: str,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    target = normalize_username(username)
    with SessionLocal() as session:
        otp_stmt = (
            select(PreKey)
            .where(
                PreKey.user_id == target,
                PreKey.is_otp == True,
                PreKey.consumed_at.is_(None),
            )
            .order_by(PreKey.created_at.asc())
            .limit(1)
        )
        pre_key = session.scalars(otp_stmt).first()
        if pre_key is None:
            return {"pre_key": None}
        pre_key.consumed_at = utcnow()
        session.commit()
        return {"pre_key": pre_key.as_dict()}


@app.post("/messages")
async def post_message(
    payload: MessageRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    message = store_message(payload.packet, user["id"])
    record_event(
        "CIPHERTEXT_STORED",
        user["id"],
        {"message_id": message["id"], "recipient_user_id": message["recipient_user_id"]},
        request=request,
    )
    await manager.send(message["recipient_user_id"], {"type": "encrypted_message", "message": message})
    return {"message": message}


@app.get("/messages/offline")
def offline_messages(
    peer: str | None = None,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    peer_id = normalize_username(peer) if peer else None
    with SessionLocal() as session:
        rows = session.scalars(select(Message).order_by(Message.seq)).all()
        messages = []
        for message in rows:
            involves_user = user["id"] in (message.sender_user_id, message.recipient_user_id)
            involves_peer = (
                peer_id is None
                or peer_id in (message.sender_user_id, message.recipient_user_id)
            )
            if involves_user and involves_peer:
                messages.append(message.as_dict())
    return {"messages": messages}


@app.get("/lab/messages")
def lab_messages(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        rows = session.scalars(select(Message).order_by(Message.seq)).all()
        result = []
        for message in rows:
            if user["id"] not in (message.sender_user_id, message.recipient_user_id):
                continue
            packet = message.packet
            result.append(
                {
                    "id": message.id,
                    "sender_user_id": message.sender_user_id,
                    "recipient_user_id": message.recipient_user_id,
                    "message_number": message.message_number,
                    "nonce": packet.get("nonce"),
                    "ciphertext": packet.get("ciphertext"),
                    "tag": packet.get("tag"),
                    "plaintext": None,
                    "plaintext_exposed": False,
                    "server_received_at": message.as_dict()["server_received_at"],
                }
            )
    record_event(
        "SERVER_COMPROMISE_VIEWED",
        user["id"],
        {"visible_rows": len(result)},
        severity="warning",
        request=request,
    )
    return {"messages": result}


@app.post("/lab/replay")
def lab_replay(
    payload: ReplayRequest, request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    with SessionLocal() as session:
        message = session.scalars(
            select(Message).where(Message.id == payload.message_id)
        ).first()
        packet = message.packet if message else None
        involved = message and user["id"] in (
            message.sender_user_id,
            message.recipient_user_id,
        )
    if not message or not involved:
        raise HTTPException(status_code=404, detail="Message not found")
    record_event(
        "REPLAY_PACKET_PREPARED",
        user["id"],
        {"message_id": payload.message_id},
        severity="warning",
        request=request,
    )
    return {"packet": packet, "expected_result": "REPLAY_REJECTED"}


@app.post("/lab/tamper")
def lab_tamper(
    payload: ReplayRequest, request: Request, user: dict[str, Any] = Depends(current_user)
) -> dict[str, Any]:
    with SessionLocal() as session:
        message = session.scalars(
            select(Message).where(Message.id == payload.message_id)
        ).first()
        stored_packet = copy.deepcopy(message.packet) if message else None
        involved = message and user["id"] in (
            message.sender_user_id,
            message.recipient_user_id,
        )
    if not message or not involved:
        raise HTTPException(status_code=404, detail="Message not found")
    packet = stored_packet
    ciphertext = base64url_decode(packet["ciphertext"])
    if ciphertext:
        tampered = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]
    else:
        tampered = b"x"
    packet["ciphertext"] = base64url_encode(tampered)
    record_event(
        "TAMPER_PACKET_PREPARED",
        user["id"],
        {"message_id": payload.message_id},
        severity="warning",
        request=request,
    )
    return {"packet": packet, "expected_result": "TAMPER_REJECTED"}


@app.post("/lab/key-substitution")
def lab_key_substitution(
    payload: KeySubstitutionRequest,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    target = normalize_username(payload.username)
    with SessionLocal() as session:
        exists = session.get(User, target) is not None
    if not exists:
        raise HTTPException(status_code=404, detail="User does not exist")
    record_event(
        "KEY_SUBSTITUTION_WARNING",
        user["id"],
        {"target_user_id": target, "note": "Client should compare fingerprints before trusting key"},
        severity="warning",
        request=request,
    )
    return {
        "target_user_id": target,
        "expected_result": "KEY_SUBSTITUTION_WARNING",
        "warning": "Public key fingerprint changed. Verify safety number before sending.",
    }


@app.post("/lab/state-compromise")
def lab_state_compromise(
    payload: StateCompromiseRequest,
    request: Request,
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
    record_event("DH_REKEY_RECOVERED", user["id"], result, request=request)
    return {"metrics": result}


@app.get("/lab/events")
def lab_events(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with SessionLocal() as session:
        stmt = (
            select(SecurityEvent)
            .where(SecurityEvent.actor_user_id.in_((None, user["id"])))
            .order_by(SecurityEvent.seq)
        )
        events = [event.as_dict() for event in session.scalars(stmt).all()]
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
        with SessionLocal() as session:
            user_exists = session.get(User, user_id) is not None
        if not user_exists:
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
    reset_db()


if WEB_DIR.exists():
    app.mount("/src", StaticFiles(directory=WEB_DIR / "src"), name="web-src")
    assets_dir = WEB_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/admin")
def admin_index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
