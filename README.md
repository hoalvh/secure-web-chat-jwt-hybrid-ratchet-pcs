# Secure Web Chat with JWT Authentication, Hybrid Ratchet and Post-Compromise Security

A Cryptography course project about secure one-to-one web chat. The project separates normal web authentication from end-to-end message encryption: JWT authorizes access to the server, while message confidentiality depends on browser-side device keys and per-message encryption keys.

The current repository is a runnable course prototype. It is intentionally smaller than the original full-stack plan so the crypto flow, threat model, and Security Lab scenarios can be demonstrated from one local FastAPI server.

This is not a production secure messenger and not a full Signal implementation.

## Team

Institution: Ho Chi Minh City University of Technology and Engineering (HCM-UTE)

| Name | GitHub | Primary Area |
|---|---|---|
| Ly Van Huu Hoa | [@hoalvh](https://github.com/hoalvh) | Application security, authentication, backend relay, Security Lab backend |
| Le Quang Minh | [@hnhat1234](https://github.com/hnhat1234) | E2EE protocol, key schedule, ratchet, protocol testing |
| Tran Quoc Truong | [@siberlly](https://github.com/siberlly) | Frontend security UX, client state, evaluation UI |

Team responsibilities and execution plan: [docs/00-project/team-and-execution-plan.md](docs/00-project/team-and-execution-plan.md)

## Current Implementation

The current MVP includes:

- Register and login with Argon2id password hashing.
- HMAC-SHA256 JWT access tokens and refresh-token cookies.
- Device public key registration.
- Browser-generated ECDH P-256 device keys.
- Local private-key storage in IndexedDB.
- One-to-one ciphertext relay over REST and WebSocket notification.
- Browser-side ECDH, HKDF-SHA256, and AES-GCM encryption/decryption.
- AES-GCM associated data over the canonical packet header.
- Security Lab scenarios for server compromise, stolen JWT, replay, tamper, key substitution, and PCS rekey metrics.
- Pytest tests for the FastAPI backend and ciphertext-only storage rules.

## Run Locally

Recommended Windows/PowerShell path after cloning from GitHub:

```powershell
git clone <repo-url>
cd secure-web-chat-jwt-hybrid-ratchet-pcs
.\scripts\setup_windows.ps1
.\scripts\test.ps1
.\scripts\run_dev.ps1
```

If PowerShell blocks local scripts on a new machine, run the same commands with a temporary execution-policy bypass:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_dev.ps1
```

Open:

```text
http://127.0.0.1:8000
```

Manual equivalent from the repository root:

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

To reset local demo data before recording or presenting:

```powershell
.\scripts\reset_demo_data.ps1
```

Suggested demo accounts:

```text
alice / pass1234
bob   / pass1234
```

Register both users in the browser. Each account creates or reuses a local browser device key and publishes only the public key to the server.

## Demo Flow

1. Register `alice`.
2. Register `bob`.
3. Login as `alice`, open `bob`, and send a message.
4. Logout, login as `bob`, open `alice`, and refresh.
5. Confirm Bob decrypts locally in the browser.
6. Run the Security Lab buttons: Server DB, Stolen JWT, Replay, Tamper, Key change, and PCS rekey.

The server lab dump should show ciphertext, nonce, tag, and routing metadata, but no plaintext message content and no private key material.

## Architecture

```text
+-------------------+        REST/JWT         +----------------------+
| Alice Web Client  | <---------------------> | FastAPI Server       |
| - session token   |                         | - Argon2id password  |
| - IndexedDB key   |        WebSocket        | - JWT verification   |
| - E2EE crypto     | <---------------------> | - Key directory      |
+-------------------+                         | - Ciphertext relay   |
          |                                   | - Security Lab APIs  |
          | E2EE ciphertext only              +----------+-----------+
          v                                              |
+-------------------+                                    |
| Bob Web Client    |                         +----------v-----------+
| - IndexedDB key   |                         | Local JSON demo store|
| - Decrypt locally |                         | - users/sessions     |
| - Security states |                         | - public keys only   |
+-------------------+                         | - encrypted packets  |
                                              +----------------------+
```

JWT is used for server access. It does not encrypt or decrypt messages. Private keys stay in the browser, and the backend rejects device submissions that include private JWK material.

## Technology Stack

| Layer | Current technology | Role |
|---|---|---|
| Backend | Python + FastAPI | Auth, refresh sessions, device/key APIs, ciphertext relay, lab endpoints |
| Frontend | HTML + CSS + vanilla JavaScript | Login, chat UI, Security Lab, browser crypto |
| Auth | Argon2id, HMAC-SHA256 JWT, HttpOnly refresh cookie | Password login and API/WebSocket authorization |
| Realtime | FastAPI WebSocket plus REST polling fallback | Notify recipient clients about new encrypted packets |
| Storage | Local JSON store under `data/` | Demo persistence for users, refresh sessions, devices, messages, and lab events |
| Client crypto | Browser Web Crypto API | ECDH P-256, HKDF-SHA256, AES-GCM, SHA-256 fingerprints |
| Client private state | IndexedDB | Browser device private key and safety/fingerprint state |
| Tests | Pytest + FastAPI TestClient | Backend smoke and security-boundary tests |

PostgreSQL, Prisma, React, TypeScript, Tailwind, Playwright, and fuller benchmark tooling remain reasonable future expansion paths, but they are not the stack used by the current runnable MVP.

## API Surface

Auth:

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /me
```

Users, devices, and keys:

```text
GET  /users
POST /devices
GET  /devices
GET  /keys/bundle/{username}
```

Messages and realtime:

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

## Repository Layout

```text
secure-web-chat/
|-- README.md
|-- requirements.txt
|-- .env.example
|-- apps/
|   |-- server/
|   |   |-- main.py
|   |   `-- tests/
|   `-- web/
|       |-- index.html
|       `-- src/
|-- docs/
`-- scripts/
```

| Directory | Purpose |
|---|---|
| `apps/server/` | Current FastAPI backend and backend tests |
| `apps/web/` | Current browser UI, Web Crypto E2EE logic, and styling |
| `docs/` | Project docs, design decisions, protocol notes, evaluation plan |
| `scripts/` | Setup, test, run, and reset helpers for Windows/PowerShell |

## Documentation

| Document | Purpose |
|---|---|
| [docs/README.md](docs/README.md) | Documentation index |
| [Team and Execution Plan](docs/00-project/team-and-execution-plan.md) | Roles, ownership, milestones, branch workflow |
| [Project Scope and Non-Goals](docs/00-project/project-scope.md) | MVP depth, non-goals, storage scope, algorithm scope |
| [Technology Decisions](docs/00-project/technology-decisions.md) | Current stack choices, trade-offs, future expansion |
| [Repository Hygiene](docs/00-project/repository-hygiene.md) | GitHub setup, `.env` rules, secret-handling notes |
| [GitHub Publish Checklist](docs/00-project/github-publish-checklist.md) | Files to keep, files to ignore, and fresh-clone run checks |
| [Threat Model](docs/01-design/threat-model.md) | Assets, trust boundaries, attacker scenarios |
| [Authentication and JWT](docs/01-design/authentication-and-jwt.md) | Auth flow, JWT, refresh session, WebSocket auth |
| [Device Identity and Key Binding](docs/01-design/device-identity-and-key-binding.md) | Device keys, public key binding, fingerprint warnings |
| [E2EE Protocol Design](docs/01-design/e2ee-protocol-design.md) | Packet format and encrypted messaging protocol |
| [Key Schedule and Ratchet](docs/01-design/key-schedule-and-ratchet.md) | Root keys, chain keys, message keys, ratchet limitations |
| [Security UX](docs/01-design/security-ux.md) | UI states for encryption, warnings, and lab evidence |
| [Experiment Plan](docs/02-evaluation/experiment-plan.md) | Server compromise, stolen JWT, replay, tamper, FS, PCS |
| [Risks, Goals, Solution, Architecture, Demo](docs/02-evaluation/risks-goals-solution-architecture-demo.md) | Clear risks-to-goals mapping, architecture, demo results, and commands |

## Tests

Run:

```powershell
python -m pytest apps/server/tests
```

The current backend tests cover register/login, device public key storage, ciphertext-only message storage, lab dump behavior, and rejection of message packets that contain plaintext.

## Security Constraints

- Do not store plaintext messages on the server.
- Do not accept private keys in device registration.
- Do not store long-lived access tokens in `localStorage`.
- Do not pass JWTs through WebSocket URL query strings.
- Use authenticated encryption with stable associated data for encrypted message packets.
- Keep experiment results reproducible and separate from source code.

## Limitations

- The current store is a JSON demo store, not PostgreSQL.
- The current protocol is a simplified course implementation, not full Signal.
- The DH rekey/PCS behavior is currently represented in the Security Lab metrics rather than a complete production double-ratchet message flow.
- IndexedDB keeps the demo usable across reloads, but it does not protect against XSS, malware, or malicious browser extensions.
- Browser private keys are extractable in the current demo so the Web Crypto flow is easier to inspect and rerun.
- Playwright UI tests and full benchmark result files have not been added yet.

Repository hygiene details: [docs/00-project/repository-hygiene.md](docs/00-project/repository-hygiene.md)
