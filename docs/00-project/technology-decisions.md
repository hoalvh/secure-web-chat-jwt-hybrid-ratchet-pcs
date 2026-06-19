# Technology Decisions

This document records the technology choices that match the current runnable implementation. Earlier project planning mentioned a larger React/Fastify/PostgreSQL/Prisma stack; those remain future expansion options, not the current MVP stack.

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
| Frontend | HTML + CSS + vanilla JavaScript | No build step, easy demo, direct access to Web Crypto and IndexedDB |
| Auth | Argon2id + HMAC-SHA256 JWT + refresh cookie | Demonstrates password hashing, short-lived access tokens, and revocable refresh sessions |
| Realtime | FastAPI WebSocket plus REST fallback | Shows explicit WebSocket auth while keeping the demo reliable through polling |
| Server storage | Local JSON store in `data/demo_store.json` | Simple inspectable persistence for course demos and tests |
| Client crypto | Browser Web Crypto API | Provides reviewed browser primitives for ECDH P-256, HKDF-SHA256, AES-GCM, SHA-256 |
| Client state | IndexedDB | Persists browser private key and safety state across reloads |
| Tests | Pytest + FastAPI TestClient | Verifies backend auth, device, ciphertext, and lab boundaries |

## 3. Architecture Decision

The project uses a modular layered repository:

- `apps/web/` contains the browser UI, IndexedDB state, and Web Crypto E2EE logic.
- `apps/server/` contains FastAPI routes for auth, device/key APIs, ciphertext relay, WebSocket auth, and lab controls.
- `docs/` contains design evidence, evaluation notes, and grading artifacts.
- `scripts/` contains setup, test, run, and reset helpers.

Classic MVC is not the main organizing model because the hard part is protocol state: root keys, chain keys, message counters, associated data, replay handling, and compromise-recovery experiments. Keeping server, browser, and protocol documentation separate makes the trust boundary easier to review.

## 4. Frontend Stack

### Vanilla JavaScript

The current UI is written in plain browser JavaScript in `apps/web/src/app.js`.

Reasons:

- No bundler or package install is required to run the demo.
- Web Crypto and IndexedDB are available directly in the browser.
- The app surface is small: login/register, contact selection, encrypted chat, and Security Lab controls.
- It keeps the course demo easy to inspect during presentation.

Trade-off: plain JavaScript gives less type safety and less component structure than React/TypeScript. If the UI grows, React + TypeScript + Vite would be a reasonable next step.

### CSS

The current UI uses a single CSS file at `apps/web/src/styles.css`.

Reasons:

- Security badges and lab panels are easier to keep stable in a small static stylesheet.
- There is no Tailwind build step.
- The screenshots remain predictable for report evidence.

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

### Local JSON Store

The current server persists demo data in `data/demo_store.json`.

Stored data includes:

- Users and password hashes.
- Refresh session hashes and expiration.
- Device public keys and fingerprints.
- Encrypted message packets.
- Security Lab events.

This is intentionally inspectable for the server-compromise lab. It is not a production database. PostgreSQL plus migrations can replace it later when the team needs stronger relational constraints and multi-user durability.

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

Refresh tokens are opaque random values stored in an HttpOnly cookie. The server stores only their SHA-256 hash in the JSON demo store. Logout marks matching sessions as revoked and deletes the cookie.

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

## 9. Future Expansion Path

| Future item | Why it may be useful | Current status |
|---|---|---|
| React + TypeScript + Vite | Larger UI, typed state, reusable components | Not used by current MVP |
| Tailwind CSS | Faster repeated security-state styling | Not used by current MVP |
| PostgreSQL | Durable relational storage and constraints | Not used by current MVP |
| Prisma or SQLAlchemy | Reproducible schema/migrations | Reserved for later |
| Playwright | Browser evidence for warnings/lab states | Planned |
| k6 or similar | Scenario benchmarks | Planned |

## 10. Decision Summary

| Decision | Main reason | Main trade-off |
|---|---|---|
| FastAPI | Small readable backend with REST, WebSocket, and tests | Python app is separate from browser JS protocol code |
| Vanilla JS | No build step and direct Web Crypto access | Less type safety than TypeScript |
| IndexedDB | Local private key persists across reloads | Does not protect against XSS/malware |
| JSON demo store | Easy to inspect for lab evidence | Not production durable or relational |
| Argon2id | Strong password hashing for login | Needs tuned parameters and dependency install |
| HMAC-SHA256 JWT | Simple local authorization | Production should use stronger key management and a JWT library |
| Web Crypto P-256/HKDF/AES-GCM | Reviewed browser primitives | Not a full Signal algorithm set |
| Pytest | Fast backend verification | Browser UI still needs automated tests |

## 11. Reference Points

These references justify tool selection and design direction. The project still needs its own implementation, tests, and experiment results.

- FastAPI documentation: https://fastapi.tiangolo.com/
- Pytest documentation: https://docs.pytest.org/
- MDN Web Crypto API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API
- MDN IndexedDB API: https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API
- OWASP Password Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- OWASP JSON Web Token Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- PostgreSQL documentation for future database work: https://www.postgresql.org/docs/
- Playwright documentation for future browser tests: https://playwright.dev/docs/intro
