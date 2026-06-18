# Secure Web Chat Course Prototype

This repository contains a runnable secure one-to-one web chat prototype for an Applied Cryptography final project.

The implementation follows the course plan in `Secure-Web-Chat-Project-Plan.md`:

- JWT authenticates browser sessions to the server.
- Device keys stay in the browser.
- The server stores public keys, routing metadata, and ciphertext only.
- The browser uses Web Crypto ECDH P-256, HKDF-SHA256, and AES-GCM.
- Message headers are bound as AES-GCM associated data.
- A simplified symmetric ratchet derives a fresh message key for each message.
- Security Lab screens demonstrate server compromise, stolen JWT, replay, tamper, key-substitution warning, and DH rekey recovery metrics.

This is a course prototype, not a production secure messenger and not a full Signal implementation.

## Current Stack

| Layer | Implementation |
|---|---|
| Backend | Python + FastAPI |
| Auth | Argon2id password hash, HMAC-SHA256 JWT, refresh cookie |
| Realtime | FastAPI WebSocket auth frame plus REST fallback |
| Storage | Local JSON demo store under `data/` |
| Frontend | HTML + CSS + vanilla JavaScript |
| Client crypto | Browser Web Crypto API |
| Local private-key storage | IndexedDB |
| Short-lived access token | `sessionStorage` so F5 keeps the demo session |
| Tests | Pytest + FastAPI TestClient |

PostgreSQL/SQLAlchemy can be added later, but the current MVP is intentionally small so the crypto and lab flows are easy to run and present.

## Run Locally

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:JWT_SECRET="change-this-for-local-demo"
python -m uvicorn apps.server.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
```

Recommended demo accounts:

```text
alice / pass1234
bob   / pass1234
```

Register both users in the browser. Each login automatically creates a local ECDH device key if one does not already exist.

## Demo Flow

1. Register Alice.
2. Register Bob.
3. Login as Alice and open Bob.
4. Send an encrypted message.
5. Logout, login as Bob, open Alice, and refresh.
6. Bob decrypts locally in the browser.
7. Open Security Lab and run:
   - Server DB.
   - Stolen JWT.
   - Replay.
   - Tamper.
   - Key change.
   - PCS rekey.

The server lab dump shows ciphertext, nonce, tag, and routing metadata, but no plaintext.

The chat view refreshes automatically while a contact is open. The server sends WebSocket notifications for new ciphertext packets, and the frontend also polls every 2.5 seconds as a fallback.

## API Surface

Auth:

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /me
```

Device and key directory:

```text
POST /devices
GET  /devices
GET  /users
GET  /keys/bundle/{username}
```

Messages:

```text
POST /messages
GET  /messages/offline?peer={username}
WS   /ws
```

Security Lab:

```text
GET  /lab/messages
POST /lab/replay
POST /lab/tamper
POST /lab/key-substitution
POST /lab/state-compromise
GET  /lab/events
```

## Security Boundaries

The backend must not receive plaintext messages or private keys. It rejects message packets containing a `plaintext` field and rejects device registration if a JWK contains private key material.

JWT is only for server access. A stolen JWT can fetch ciphertext while it is valid, but it cannot decrypt messages without the browser's local private key and ratchet state.

The browser encrypts with:

```text
ECDH P-256 shared secret
-> HKDF-SHA256 root key
-> directional chain key
-> per-message AES-GCM key
```

The AES-GCM associated data is the canonical packet header, including sender, recipient, device IDs, conversation ID, message number, and ratchet public-key fingerprint. Modifying the header or ciphertext causes decrypt failure.

## Tests

Run:

```powershell
python -m pytest apps/server/tests
```

The backend tests cover:

- Register/login.
- Public device-key storage.
- Ciphertext-only message storage.
- Lab dump without plaintext exposure.
- Rejection of message packets that include plaintext.

## Repository Layout

```text
apps/server/main.py        FastAPI backend and lab endpoints
apps/server/tests/         Backend smoke tests
apps/web/index.html        Single-page chat and Security Lab UI
apps/web/src/app.js        Web Crypto E2EE and UI logic
apps/web/src/styles.css    App styling
docs/                      Design notes and report material
experiments/               Scenario folders for later evidence
benchmarks/                Benchmark scripts and results
```

## Limitations

- The demo store is JSON, not PostgreSQL.
- The ratchet is simplified for course evidence.
- The frontend stores extractable demo private keys in IndexedDB so the project can be rerun easily.
- Browser XSS, malicious extensions, full multi-device sync, full Signal X3DH/Double Ratchet, key transparency, and PQC are future work.
