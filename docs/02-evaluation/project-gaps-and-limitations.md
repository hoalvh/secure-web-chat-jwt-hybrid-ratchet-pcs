# Project Gaps and Limitations

This document is an honest record of what the project still lacks compared with a
production secure-messaging system. The core demo works, but several areas remain
at prototype / course-MVP level.

## 1. Short Summary

Already implemented:

- Register/login on FastAPI.
- Argon2id password hashing (with a dev-only scrypt fallback).
- JWT access tokens and a refresh-token cookie.
- Browser-generated ECDH keys; private key stored in IndexedDB.
- Public key published to the server.
- Message encryption/decryption with the Web Crypto API.
- Server stores only ciphertext, nonce, tag, and metadata.
- **A real database**: SQLAlchemy with SQLite (local) / PostgreSQL (deploy) via `DATABASE_URL`, foreign keys and cascade rules, a normalised `conversations` table, and **Alembic migrations**.
- Expired refresh sessions are cleaned up; the event log records severity, IP, and user-agent.
- Admin dashboard (Tabler) showing password hashes, refresh-token hashes, public keys, conversations, ciphertext, and the event log.
- Normal users only chat and inspect keys/fingerprints (Bootstrap UI; chat flicker fixed).
- 9 backend tests (API boundaries + database integrity).
- A `scripts/decrypt_message.mjs` helper to manually decrypt one ciphertext (being updated to read the database instead of the old JSON store).

Not production-ready because:

- The crypto protocol is not full Signal / Double Ratchet; PCS is only a simulated metric.
- No key backup/recovery or key export/import.
- No hardening against XSS/malware/malicious extensions; no rate limiting; no CSP/security headers.
- No real deployment (Dockerfile/CI-CD/HTTPS) and no monitoring.
- Admin has no filter/search/pagination/export; the WebSocket manager is in-memory (single worker).

## 2. Storage and Database Gaps

Most of this area is **now complete** (migrated from a JSON store to SQLAlchemy + Alembic).

| Area | Current | Missing |
|---|---|---|
| Server storage | SQLAlchemy: SQLite (local) / PostgreSQL (deploy) via `DATABASE_URL`, with indexes and transactions | Retention/archival, read replicas, sharding |
| Migration | Alembic (`migrations/`), `alembic upgrade head` on deploy | — |
| User table | `users` table, unique `username`, primary key | (Wallet address if extended to Web3) |
| Session table | `refresh_sessions` table, FK to users, expired sessions cleaned up on login/refresh | Rotating the refresh token on every refresh |
| Device table | `devices` table, FK to users, `revoked_at` column | Revoke endpoint/UI; multi-device fan-out |
| Conversation table | Normalised `conversations` table (participants, last_message_at) | — |
| Message table | `messages` table, FK to conversations/users, indexed sender/recipient/conversation + `message_number` | Query pagination |
| Event log | `security_events` table with severity + actor IP + user-agent | Long-term retention policy |
| Data integrity | Foreign keys + ON DELETE CASCADE/SET NULL (tested) | — |
| Backup | Managed Postgres provider backups | Dedicated export/restore script |

## 3. UI and UX Gaps

The interface was rebuilt with **Tabler (admin) + Bootstrap (chat)** over a CDN (no build step). Visuals/layout are solid; what remains is mostly UX functionality.

| Area | Current | Missing |
|---|---|---|
| Login/register | Compact Tabler card | Realtime validation, forgot password, detailed error states |
| User chat UI | One-to-one chat, contact list, fingerprint, chat bubbles (flicker fixed) | Search, unread count, typing, delivery/read receipts |
| Admin dashboard | Cards + tables (sticky header, zebra), conversations, coloured severity, Source IP/agent column | Filter, search, pagination, export |
| Key warning UI | Fingerprint/key-state badge | A proper safety-number verification flow |
| Mobile responsive | Bootstrap/Tabler responsive grid | Thorough multi-viewport testing |
| Accessibility | Improved via Tabler components | Full keyboard-nav/ARIA audit |
| Loading/error state | Basic (badges) | Skeleton/loading and retry UX |

## 4. Cryptography and Protocol Gaps

| Area | Current | Missing | Upgrade path |
|---|---|---|---|
| Device key | ECDH P-256 browser key | No identity key + signed prekey + one-time prekey | Design X3DH or an equivalent |
| Key exchange | Direct ECDH via the public key directory | No complete defense against server key substitution | Key transparency or signed key bundles |
| Message key | HKDF per-message key | Not a full Double Ratchet | Implement a full Double Ratchet |
| Replay handling | Demo packet ID / message number | No production replay window | Store receive counters / skipped keys |
| Tamper detection | AES-GCM AAD header | Good for the demo, needs broader tests | Test header/ciphertext/tag changes thoroughly |
| PCS | Lab metric / concept | No real DH-ratchet message flow | Add real ratchet steps and rekeying |
| Group chat | None | No group E2EE | Research MLS or group sessions |
| File/media encryption | None | Cannot send files | Add file-chunk encryption / key wrapping |

This project borrows Signal's ideas but is not a Signal implementation.

## 5. Browser Key and Recovery Gaps

| Area | Current | Missing | Upgrade path |
|---|---|---|---|
| Private key storage | IndexedDB | Losing browser data loses the key | Add a backup/recovery phrase |
| Recovery phrase | None | User cannot restore the key on a new machine | Generate 12/24 words or a backup code via CSPRNG |
| Key export | None | No encrypted private-key export | Export a wrapped/encrypted private key |
| Key import | None | No import when switching machines | Import from a recovery phrase or backup file |
| Manual decrypt export | Can export temporarily for `scripts/decrypt_message.mjs` | Debug/evidence only, not a safe backup | Add an encrypted export/import flow |
| Endpoint compromise | Not handled | Malware/XSS can still read keys in the browser | CSP, sanitisation, security audit; do not claim protection against a compromised machine |
| MetaMask/wallet identity | None | No wallet connection or signed key binding | Use MetaMask to sign an identity/key binding (never export the wallet private key) |

A recovery phrase protects against losing the key when switching machines; it does not protect against an attacker who has already compromised the machine.

## 6. Authentication and Authorization Gaps

| Area | Current | Missing | Upgrade path |
|---|---|---|---|
| Password auth | Username/password + hash | No password reset, email verification, rate limit | Add a reset flow and rate limiting |
| JWT | Hand-written HMAC-SHA256 for the demo | Production should use a vetted JWT library | Use PyJWT/authlib and key rotation |
| Refresh token | HttpOnly cookie + hash | No strict refresh-token rotation | Rotate the refresh token on every refresh |
| Admin role | Username in `ADMIN_USERNAMES` | No role table / permission model | RBAC with roles/permissions in the DB |
| Brute-force defense | None | Login brute force is unbounded | Rate limit per IP/user |
| MFA | None | No 2FA | TOTP/WebAuthn |
| Wallet login | None | No Sign-In with Ethereum | Nonce + MetaMask signature + JWT |

Authentication is sufficient for a local demo but not enough to resist brute force or run on the public internet.

## 7. Admin Dashboard Gaps

| Area | Current | Missing | Upgrade path |
|---|---|---|---|
| View users | Username/password hash | No filter/search | Search by username/role |
| View ciphertext | Nonce/ciphertext/tag | No conversation/time filter | Filter by user, conversation, date |
| View devices | Public key/fingerprint | No revoke from the UI | Revoke device button |
| View sessions | Refresh-token hash | No revoke from the UI | Revoke session button |
| View events | Event table with severity + IP + user-agent | No pagination/export | Event export to CSV |
| Admin security | `require_admin` guard | No strong audit of admin actions | Audit IP, user-agent, action detail |

The admin dashboard is an observation view over the server store, not a complete admin console.

## 8. Realtime and Messaging Gaps

| Area | Current | Missing | Upgrade path |
|---|---|---|---|
| WebSocket notify | `/ws` with JWT auth | No good reconnect/backoff | Reconnect strategy |
| Polling fallback | 2.5s refresh of the active chat | Wasteful as the user count grows | More reliable server push |
| Delivery status | None | No delivered/read state | Add delivery/read receipts |
| Offline queue | Basic `/messages/offline` | No pagination, ack, cleanup | Message cursor + ack |
| Conversation model | **Normalised `conversations` table** (FK to users) | No conversation-list API for the user UI | Add a conversation-list endpoint |
| Multi-device | `devices` schema already allows multiple devices per user | App logic still uses one device; no encrypt fan-out | Encrypt per device key |

## 9. Testing Gaps

| Area | Current | Missing | Upgrade path |
|---|---|---|---|
| Backend tests | 9 pytest (API boundary + DB integrity: FK/cascade/conversation/cleanup/severity) | Not every endpoint / edge case covered | Add negative tests |
| Frontend tests | `node --check`; Playwright run ad-hoc for verification/screenshots | No committed Playwright suite in the repo | Add E2E tests for login/chat/admin |
| Crypto tests | Indirect, via the demo | No independent test vectors | Test vectors for the HKDF/AES-GCM packet |
| Manual decrypt script | `scripts/decrypt_message.mjs` | No automated fixture/test for many packets | Add fixed test vectors for the script |
| Security tests | Plaintext rejection / admin 403 | No packet fuzzing or header tampering | Fuzz packet validation |
| Performance tests | None | No latency/throughput measured | Benchmark login/encrypt/decrypt/relay |
| Cross-browser tests | None | No Chrome/Edge/Firefox/Mobile testing | Browser matrix |

## 10. Deployment and Operations Gaps

| Area | Current | Missing | Upgrade path |
|---|---|---|---|
| Local run | Windows setup/run/test scripts | No real server deployment | Docker or VM/cloud deploy |
| HTTPS | Local HTTP | Production requires HTTPS | Reverse proxy (Nginx/Caddy) + TLS |
| Secrets | `JWT_SECRET` env var | No secret manager/rotation | Secret manager and key rotation |
| Logging | Event log in the DB (severity + IP + user-agent) | No structured app logs/monitoring | App logs + metrics |
| Error handling | Basic | No centralised error handling | Error middleware |
| CI/CD | None | Tests do not run automatically on push | GitHub Actions |
| Data migration | **Alembic in place** (`migrations/`) | — | `alembic upgrade head` on deploy |

## 11. Privacy and Security Hardening Gaps

| Area | Current | Missing |
|---|---|---|
| XSS protection | Not a focus yet | CSP, input sanitisation, dependency audit |
| CSRF | Refresh cookie is SameSite=Lax | Review carefully if more cookie endpoints are added |
| Rate limit | None | Login/API rate limiting |
| Content Security Policy | None | CSP header |
| Secure cookie | `secure=False` for the local demo (`COOKIE_SECURE` switch exists) | Must be `secure=True` over HTTPS in production |
| Token storage | Access token in sessionStorage | Needs a deeper XSS-risk assessment |
| Admin data exposure | Admin views hashes/ciphertext | Stronger audit/logging and finer authorization |
| Device revocation | `revoked_at` field, no UI/endpoint | Revoke lost/compromised devices |

## 12. Scope Not Implemented Yet

- React/Vue/Next frontend (currently vanilla JS + Tabler/Bootstrap).
- Full Signal protocol.
- X3DH handshake.
- Signed prekeys.
- One-time prekeys.
- Full Double Ratchet.
- Group chat.
- Encrypted file/image upload.
- Push notifications.
- Mobile app.
- MetaMask wallet login.
- Recovery phrase / key import-export.
- Multi-device fan-out encryption.
- Production deployment.
- CI/CD.
- A real benchmark dashboard.

## 13. Suggested Next Milestones

Completed: ✅ moved to SQLite/PostgreSQL (SQLAlchemy), ✅ explicit schema + migrations (Alembic) for users, sessions, devices, conversations, messages, events, ✅ Tabler/Bootstrap UI.

Suggested order from here:

1. **Real Double Ratchet + PCS** (matches the project title — highest priority for a cryptography course).
2. Real deployment: Dockerfile + host + domain + HTTPS, and CI/CD (GitHub Actions running tests).
3. Rate limiting for auth endpoints + CSP/security headers.
4. Recovery phrase or encrypted key backup/export/import.
5. Filter/search/pagination + revoke device/session buttons for the admin dashboard.
6. A Playwright E2E test suite for login/chat/admin.
7. Update `scripts/decrypt_message.mjs` to read the database instead of JSON.
8. (Optional) Wallet login / MetaMask identity binding for a Web3 direction.

## 14. Summary

```text
Current project = runnable cryptography course prototype.

Already done:
- JWT auth
- browser-side E2EE demo
- ciphertext-only storage on a real database (SQLite local / PostgreSQL deploy, SQLAlchemy + Alembic, foreign keys)
- admin dashboard (Tabler) for hashes/ciphertext/conversations/events with severity + IP
- user chat (Bootstrap) + key/fingerprint view

Still missing:
- full Signal / Double Ratchet (real PCS, not just a lab metric)
- key recovery + encrypted key export/import
- hardening: rate limit, CSP/security headers, XSS/endpoint compromise
- deployment, CI/CD, monitoring
- admin filter/search/pagination, device/session revoke UI
```
