# Project Scope and Non-Goals

This document records what the team will build for the MVP and what will stay outside the deadline.

## 1. Scope Statement

This is a **Cryptography course project**. The core work is the secure messaging layer:

- End-to-end encryption.
- Device identity and key binding.
- Per-message key derivation.
- Symmetric ratchet.
- DH ratchet.
- Forward secrecy.
- Post-compromise security.
- Replay and tamper resistance.
- Key-substitution warning.
- Security experiments.
- Basic benchmarks.

The web application, database, UI, and local setup are included to support the demo. They should be correct and easy to run, but they are not separate research topics.

## 2. Depth by Area

| Area | Expected Depth | Reason |
|---|---|---|
| E2EE protocol | Deep | Core cryptography topic |
| Key schedule and ratchet | Deep | Required for forward secrecy and PCS |
| Threat model | Deep | Required to define attacker capabilities and claims |
| Security Lab | Deep | Shows how the design behaves under attack scenarios |
| Security benchmarks | Medium | Measures crypto, auth, and relay overhead |
| Authentication and JWT | Secure MVP | Needed for login and WebSocket access |
| Database design | Basic correctness | Needed for users, devices, messages, and lab logs |
| Frontend UI | Demo-ready security UX | Needed to show encryption, trust, and lab states |
| Deployment | Local reproducible setup | Needed for team development and grading |
| Scalability | Basic design awareness | Full distributed scaling is out of scope |

## 3. In Scope

The following are in scope:

- Register and login flow.
- Argon2id password hashing.
- Short-lived JWT access tokens.
- Refresh-token session management.
- Device registration.
- Public key bundle storage.
- Ciphertext-only message relay.
- One-to-one encrypted chat.
- Client-side private keys and ratchet state.
- Safety number or fingerprint display.
- Key-change warning.
- Security Lab attack simulations.
- Basic performance benchmarks.
- Clear documentation and reproducible demo setup.

## 4. Out of Scope

The following are out of scope for the MVP:

- Advanced database query optimization.
- Custom database indexing algorithms.
- Distributed database sharding or replication.
- High-availability deployment.
- Production Kubernetes deployment.
- Full observability stack.
- Full multi-device synchronization.
- Group messaging with MLS.
- Push notifications.
- File sharing.
- Full-text message search.
- Complex admin dashboards.
- OAuth/social login.
- MFA.
- Account recovery workflow.
- Formal verification with Tamarin or ProVerif.
- Production-grade Signal compatibility.

These topics can be mentioned as future work, but they should not take time away from the encrypted chat protocol and experiments.

## 5. Database Scope

The database supports authentication, device metadata, ciphertext storage, and lab logs.

The MVP should implement:

- Correct relational schema.
- Primary keys and foreign keys.
- Unique constraints for users and devices.
- Indexes for common lookup paths.
- Safe storage of password hashes.
- Hashed refresh-token storage.
- Public key bundle storage.
- Ciphertext message storage.
- Security event logs for experiments.

Recommended basic indexes:

| Table | Index Purpose |
|---|---|
| `users` | unique username/email lookup |
| `devices` | lookup devices by user ID |
| `public_key_bundles` | lookup active bundle by user/device |
| `refresh_sessions` | lookup active session by user/device/session ID |
| `messages` | lookup messages by conversation and creation time |
| `security_events` | lookup lab events by scenario and time |

The MVP does not include advanced database work such as:

- Query planner tuning.
- Partitioning.
- Sharding.
- Replication.
- Custom indexing structures.
- Lock-contention optimization.
- Large-scale archival strategy.

## 6. Algorithm Scope

The project uses algorithms at three levels.

| Layer | Expected Depth |
|---|---|
| Cryptographic algorithms | Use reviewed libraries and explain protocol composition |
| Application algorithms | Keep simple and correct: validation, routing, state transitions |
| Database algorithms | Use standard relational modeling, constraints, and practical indexes |

The project should not implement low-level cryptographic primitives manually. The team should focus on protocol composition, state transitions, threat model, and experiments.

## 7. Performance Scope

Performance measurement is in scope. Heavy optimization is not.

The MVP should measure:

- Login latency.
- JWT verification time.
- WebSocket connect/auth latency.
- Encrypt time per message.
- Decrypt time per message.
- DH ratchet rekey latency.
- Ciphertext overhead.
- Server relay throughput.

The project does not need to optimize for:

- Millions of concurrent users.
- Multi-region routing.
- Distributed queues.
- Database sharding.
- CDN-level optimization.
- Production SLO/SLA targets.

## 8. Evaluation Boundaries

If the project is asked about database algorithms, scalability, or missing chat features, use the scope in this document:

- Database work is limited to schema correctness, constraints, safe credential/session storage, and practical indexes.
- PostgreSQL handles indexing and query planning. The team does not implement a custom database engine or custom indexing algorithm.
- The system is not production-ready. Production work would require deployment hardening, monitoring, incident response, account recovery, MFA, multi-device support, and security review.
- Extra chat features such as avatars, files, search, read receipts, and push notifications are lower priority than E2EE, ratcheting, replay/tamper handling, and PCS experiments.

## 9. Future Work

Future extensions can include:

- Full multi-device support.
- Group messaging with MLS.
- Key transparency.
- Encrypted backup and recovery keys.
- MFA and account recovery.
- Production deployment.
- Database partitioning for large message history.
- Message search over encrypted local storage.
- Formal verification of protocol properties.

