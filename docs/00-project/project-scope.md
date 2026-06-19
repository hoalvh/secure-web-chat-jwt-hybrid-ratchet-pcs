# Project Scope and Non-Goals

This document records what the team will build for the MVP and what will stay outside the deadline.

## 1. Scope Statement

This is a Cryptography course project. The core work is the secure messaging layer:

- End-to-end encryption.
- Device identity and public key binding.
- Per-message key derivation.
- Symmetric ratchet concept.
- DH rekey/post-compromise security concept.
- Forward secrecy explanation.
- Replay and tamper resistance.
- Key-substitution warning.
- Security experiments.
- Basic benchmark or timing evidence.

The web application, local storage, UI, and server setup are included to support the demo. They should be correct and easy to run, but they are not separate product research topics.

## 2. Current MVP Depth by Area

| Area | Expected depth | Current implementation |
|---|---|---|
| E2EE protocol | Deep | Browser Web Crypto ECDH P-256, HKDF-SHA256, AES-GCM |
| Key schedule and ratchet | Deep enough for course demo | Per-message derivation plus PCS lab metric |
| Threat model | Deep | Server compromise, JWT theft, replay/tamper, key substitution, XSS limits |
| Security Lab / admin evidence | Deep | FastAPI lab endpoints plus admin dashboard evidence; normal user UI stays focused on chat and keys |
| Authentication and JWT | Secure MVP | Argon2id, HMAC-SHA256 JWT, refresh cookie |
| Storage | Demo correctness | Local JSON store under `data/`, not production database |
| Frontend UI | Demo-ready security UX | HTML/CSS/vanilla JS with user chat/key inspector and admin dashboard |
| Deployment | Local reproducible setup | Run one FastAPI app locally |
| Scalability | Design awareness only | Out of current scope |

## 3. In Scope

The following are in scope:

- Register and login flow.
- Argon2id password hashing.
- Short-lived JWT access tokens.
- Refresh-token session management.
- Device public key registration.
- Public key bundle lookup.
- Ciphertext-only message relay.
- One-to-one encrypted chat.
- Client-side private keys in IndexedDB.
- Fingerprint display.
- Key-change warning.
- Security Lab attack simulations through backend endpoints.
- Admin dashboard evidence for server-side hashes, public keys, ciphertext, and events.
- Manual decrypt helper for verifying one ciphertext with an exported browser device key.
- Basic performance/security evidence.
- Clear documentation and reproducible demo setup.

## 4. Out of Scope

The following are out of scope for the current MVP:

- Production deployment hardening.
- Full multi-device synchronization.
- Full Signal X3DH/Double Ratchet compatibility.
- Group messaging with MLS.
- Key transparency.
- Encrypted backups and recovery keys.
- Push notifications.
- File sharing.
- Full-text message search.
- Production-grade admin console with search/filter/pagination/export.
- OAuth/social login.
- MFA.
- Account recovery workflow.
- Formal verification with Tamarin or ProVerif.
- Advanced database optimization.
- Distributed database sharding or replication.

These topics can be mentioned as future work, but they should not take time away from the encrypted chat protocol and experiments.

## 5. Storage Scope

The current MVP uses a local JSON demo store. It supports:

- User records with password hashes.
- Refresh-session hashes.
- Device public key bundles.
- Ciphertext message packets.
- Security event logs.

This store is useful for the Security Lab because it is easy to inspect and prove that plaintext/private keys are absent.

The admin dashboard reads from the same store and intentionally exposes only server-side demo records: password hashes, refresh-session hashes, public keys, ciphertext, routing metadata, and security events.

The current MVP does not implement:

- PostgreSQL-backed persistence in the running app.
- Prisma/SQLAlchemy migrations.
- Foreign keys and relational constraints.
- Advanced indexes.
- Large-scale archival or retention behavior.

PostgreSQL and migrations are a future expansion path, not a current runtime requirement.

## 6. Algorithm Scope

The project uses algorithms at three levels.

| Layer | Expected depth |
|---|---|
| Cryptographic algorithms | Use reviewed browser/server libraries and explain protocol composition |
| Application algorithms | Keep simple and correct: validation, routing, state transitions |
| Storage algorithms | Use simple demo persistence now; use normal database constraints later |

The project should not implement low-level cryptographic primitives manually. The team should focus on protocol composition, state transitions, threat model, and experiments.

## 7. Performance Scope

Performance measurement is in scope. Heavy optimization is not.

The MVP should measure or at least prepare evidence for:

- Login latency.
- JWT verification time.
- WebSocket connect/auth latency.
- Encrypt time per message.
- Decrypt time per message.
- PCS rekey metric.
- Ciphertext overhead.
- Server relay latency.

The project does not need to optimize for:

- Millions of concurrent users.
- Multi-region routing.
- Distributed queues.
- Database sharding.
- CDN-level optimization.
- Production SLO/SLA targets.

## 8. Evaluation Boundaries

If the project is asked about database algorithms, scalability, or missing chat features, use the scope in this document:

- Current storage is a demo JSON store for local evidence.
- Production database design is future work.
- The system is not production-ready.
- Extra chat features such as avatars, files, search, read receipts, and push notifications are lower priority than E2EE, ratcheting concepts, replay/tamper handling, and PCS experiments.

## 9. Future Work

Future extensions can include:

- Full multi-device support.
- Group messaging with MLS.
- Key transparency.
- Encrypted backup and recovery keys.
- MFA and account recovery.
- PostgreSQL persistence with migrations.
- React/TypeScript UI refactor.
- Browser automation tests.
- Admin dashboard filtering/export.
- Manual decrypt test vectors.
- Formal verification of protocol properties.
