# Technology Decisions

This document records the technology choices that match the current runnable implementation. Earlier project planning mentioned a larger React/Fastify/Prisma stack; React and Fastify remain future expansion options. PostgreSQL is now supported for deployment (through SQLAlchemy, not Prisma).

## 1. Decision Principles

The stack is chosen using five principles:

- **Cryptographic clarity:** authentication, transport security, and end-to-end encryption must remain separate concepts.
- **Testability:** important security boundaries must be testable with small local commands.
- **Reproducibility:** the demo should run from documented PowerShell commands on a teammate machine.
- **Course fit:** cryptographic behavior must be visible enough for explanation and grading.
- **Controlled scope:** the project should stay small enough to finish as a final-project prototype.

Detailed scope boundaries are defined in [`project-scope.md`](project-scope.md).

## 2. Current Stack Summary

| Layer | Current decision | Why it fits now |
|---|---|---|
| Backend | Python + FastAPI | Small API surface, built-in OpenAPI, easy local run command, good pytest support |
| Frontend | HTML + vanilla JavaScript, styled with Tabler/Bootstrap (CDN) | No build step, easy demo, direct access to Web Crypto, IndexedDB, and admin/user UI state |
| Auth | Argon2id + HMAC-SHA256 JWT + refresh cookie | Demonstrates password hashing, short-lived access tokens, and revocable refresh sessions |
| Realtime | FastAPI WebSocket plus REST fallback | Shows explicit WebSocket auth while keeping the demo reliable through polling |
| Server storage | SQLAlchemy ORM: SQLite locally / PostgreSQL on deploy (Alembic migrations) | Real relational store with foreign keys, selectable by `DATABASE_URL`, still easy to inspect for the demo |
| Client crypto | Browser Web Crypto API | Provides reviewed browser primitives for ECDH P-256, HKDF-SHA256, AES-GCM, SHA-256 |
| Client state | IndexedDB | Persists browser private key and safety state across reloads |
| Tests/tools | Pytest + FastAPI TestClient, Node syntax/decrypt helper | Verifies backend auth/device/ciphertext/admin boundaries and allows manual ciphertext decryption checks |

## 3. Architecture Decision

The project uses a modular layered repository:

- `apps/web/` contains the browser UI, IndexedDB state, admin dashboard rendering, and Web Crypto E2EE logic.
- `apps/server/` contains FastAPI routes for auth, device/key APIs, ciphertext relay, WebSocket auth, and lab controls.
- `docs/` contains design evidence, evaluation notes, and grading artifacts.
- `scripts/` contains setup, test, run, reset, and manual decrypt helpers.

Classic MVC is not the main organizing model because the hard part is protocol state: root keys, chain keys, message counters, associated data, replay handling, and compromise-recovery experiments. Keeping server, browser, and protocol documentation separate makes the trust boundary easier to review.

## 4. Frontend Stack

### Vanilla JavaScript

The current UI is written in plain browser JavaScript in `apps/web/src/app.js`.

Reasons:

- No bundler or package install is required to run the demo.
- Web Crypto and IndexedDB are available directly in the browser.
- The app surface is small: login/register, contact selection, encrypted chat, key/fingerprint inspection, and admin dashboard.
- It keeps the course demo easy to inspect during presentation.

Trade-off: plain JavaScript gives less type safety and less component structure than React/TypeScript. If the UI grows, React + TypeScript + Vite would be a reasonable next step.

### CSS

Styling uses the **Tabler** UI kit (which is built on **Bootstrap 5**) loaded from a
CDN, plus a small custom layer at `apps/web/src/styles.css`. Tabler styles the
admin dashboard (cards, tables, page header, stat cards); its bundled Bootstrap
grid/components style the chat and auth screens. The custom layer only adds
app-specific pieces (chat bubbles, contacts list, key inspector, status/severity
badges).

Reasons:

- Tabler/Bootstrap give a professional look without writing a full design system.
- They are pulled from a CDN with a single `<link>` - **still no build step / bundler**, consistent with the vanilla-JS decision above.
- The application logic (auth, Web Crypto E2EE, IndexedDB, WebSocket) stays our own vanilla JavaScript; the frameworks only provide presentation.
- There is no Tailwind/React/Vite toolchain.

Trade-off: repeated visual patterns must be maintained manually.

### IndexedDB

IndexedDB stores local browser state:

- Device private key JWK.
- Device ID and public key.
- Contact fingerprint/safety state.

The current code uses the native IndexedDB API rather than Dexie. Dexie can be added later if the local state model becomes more complex.

Important limitation: IndexedDB does not protect against XSS, malware, or malicious browser extensions. It only keeps private keys out of the server-side store.

## 5. Backend Stack

### FastAPI

FastAPI is the current backend framework.

Reasons:

- Route handlers are compact and easy to read for a course project.
- Pydantic models validate auth/device/message request bodies.
- FastAPI supports REST and WebSocket in the same app.
- `TestClient` makes backend boundary tests straightforward.
- The same server can serve the static frontend at `/`.

### Database (SQLAlchemy)

The server persists data through SQLAlchemy (`apps/server/db.py`). One env var,
`DATABASE_URL`, selects the backend:

- **Local / default:** a SQLite file at `data/secure_chat.db` (zero setup).
- **Deployment:** a managed PostgreSQL instance (e.g. Neon/Supabase/Render). `postgres://` URLs are normalised to the psycopg driver automatically.

Tables (with foreign keys and `ON DELETE` rules):

- `users` - accounts and Argon2id password hashes.
- `refresh_sessions` - refresh-token hashes, expiry; expired rows are cleaned up on login/refresh.
- `devices` - device public keys and fingerprints.
- `conversations` - normalised one-to-one threads (participants, last message time).
- `messages` - encrypted packets, with indexed `conversation_id` / `message_number`.
- `security_events` - audit log with severity, actor IP, and user-agent.

Schema is managed by **Alembic** migrations under `migrations/` (run `alembic
upgrade head` on deploy). For local SQLite the app also creates tables on first
run, so a fresh clone works with no extra steps. The store stays inspectable for
the server-compromise / admin-dashboard demo while now giving real relational
constraints and multi-user durability.

### WebSocket

WebSocket is used for authenticated notification frames. The browser first opens `/ws`, then sends:

```json
{
  "type": "auth",
  "access_token": "jwt..."
}
```

The frontend also polls offline messages every 2.5 seconds while a conversation is open. This fallback keeps the local demo usable even when a WebSocket disconnects.

## 6. Authentication Decisions

### Argon2id

Argon2id is used through `argon2-cffi` when dependencies are installed. It is a modern password hashing choice and keeps password storage separate from message encryption.

The code includes a development fallback based on `scrypt` only so the server can fail more gracefully if dependencies are missing. The intended dependency path is still Argon2id.

### JWT

The current access token is an HMAC-SHA256 JWT created by the FastAPI app. It includes:

- `sub`
- `username`
- `session_id`
- `jti`
- `iat`
- `exp`
- `iss`
- `aud`

JWT authorizes API and WebSocket access. It does not decrypt messages and does not prove that a public key belongs to a human contact.

### Refresh Cookie

Refresh tokens are opaque random values stored in an HttpOnly cookie. The server stores only their SHA-256 hash in the `refresh_sessions` table. Logout marks matching sessions as revoked and deletes the cookie; expired sessions are purged on login/refresh.

## 7. Cryptography Decisions

### Browser Web Crypto

The current browser implementation uses Web Crypto for:

- ECDH P-256 device key generation and shared secret derivation.
- HKDF-SHA256 root, chain, and message key derivation.
- AES-GCM authenticated encryption.
- SHA-256 public key fingerprints.
- Random AES-GCM nonces.

This keeps low-level primitive implementation out of project code. The project code composes primitives into packet format, associated data, and key schedule logic.

### P-256 Instead of X25519

The current implementation uses P-256 because it is widely available in browser Web Crypto. The original Signal-inspired design can still be discussed as future work with X25519/Ed25519/libsodium, but the current code and docs should describe P-256 honestly.

### AES-GCM

AES-GCM is used because it gives confidentiality and integrity in one AEAD mode. The packet header is serialized canonically and passed as associated data, so changes to sender, recipient, device IDs, conversation ID, message number, or ratchet fingerprint cause decrypt failure.

## 8. Testing and Benchmarking

### Current Tests

The current test command is:

```powershell
python -m pytest apps/server/tests
```

The tests cover:

- Register/login.
- Device public key storage.
- Rejection of private key material.
- Ciphertext-only message storage.
- Security Lab dump without plaintext.
- Rejection of message packets that contain plaintext.

### Future Tests

Reasonable next steps:

- Browser UI automation with Playwright.
- Deterministic Web Crypto/key schedule tests.
- Scripted Security Lab evidence under `docs/02-evaluation/` or a future dedicated evidence folder.
- Benchmark outputs can be added later when real benchmark scripts exist.

### Manual Decrypt Helper

`scripts/decrypt_message.mjs` mirrors the browser key schedule with Node Web Crypto:

```powershell
node scripts\decrypt_message.mjs --list
node scripts\decrypt_message.mjs --device .\tmp\<exported-device>.json --index 0
```

It needs the stored packet plus a browser device export containing `privateKeyJwk`. (The helper currently reads the legacy JSON store and is being updated to read the SQLite database.) This is a debugging/evidence tool only; exported private keys must stay outside git.

## 9. Future Expansion Path

| Future item | Why it may be useful | Current status |
|---|---|---|
| React + TypeScript + Vite | Larger UI, typed state, reusable components | Not used by current MVP |
| Tailwind CSS | Faster repeated security-state styling | Not used (Tabler/Bootstrap used instead) |
| SQLAlchemy + Alembic | Relational models and reproducible migrations | **Implemented** in the current MVP |
| PostgreSQL | Durable relational storage and constraints | **Supported** for deployment via `DATABASE_URL` |
| Playwright | Browser evidence for chat/key/admin states | Used ad-hoc for UI screenshots (dev-only, not in `requirements.txt`) |
| k6 or similar | Scenario benchmarks | Planned |

## 10. Decision Summary

| Decision | Main reason | Main trade-off |
|---|---|---|
| FastAPI | Small readable backend with REST, WebSocket, and tests | Python app is separate from browser JS protocol code |
| Vanilla JS | No build step and direct Web Crypto access | Less type safety than TypeScript |
| IndexedDB | Local private key persists across reloads | Does not protect against XSS/malware |
| SQLite/PostgreSQL via SQLAlchemy + Alembic | Real relational store with FKs/migrations, still inspectable for lab evidence | One env var to switch backends; in-memory WebSocket manager still limits horizontal scaling |
| Argon2id | Strong password hashing for login | Needs tuned parameters and dependency install |
| HMAC-SHA256 JWT | Simple local authorization | Production should use stronger key management and a JWT library |
| Web Crypto P-256/HKDF/AES-GCM | Reviewed browser primitives | Not a full Signal algorithm set |
| Pytest + Node helper | Fast backend verification and manual ciphertext decrypt checks | Browser UI still needs automated tests |

## 11. Reference Points

These references justify tool selection and design direction. The project still needs its own implementation, tests, and experiment results.

- FastAPI documentation: https://fastapi.tiangolo.com/
- Pytest documentation: https://docs.pytest.org/
- MDN Web Crypto API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API
- MDN IndexedDB API: https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API
- OWASP Password Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- OWASP JSON Web Token Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- SQLAlchemy ORM documentation: https://docs.sqlalchemy.org/
- Alembic migrations documentation: https://alembic.sqlalchemy.org/
- PostgreSQL documentation (deployment backend): https://www.postgresql.org/docs/
- Tabler UI kit (admin/Bootstrap styling): https://tabler.io/
- Playwright documentation (UI screenshots/evidence): https://playwright.dev/docs/intro
