# Secure Web Chat with JWT Authentication, Hybrid Ratchet and Post-Compromise Security

A Cryptography course project about secure one-to-one web chat. The system combines normal web authentication with JWT, client-side device keys, end-to-end encrypted messages, a lightweight symmetric/DH ratchet, and lab scenarios for forward secrecy and post-compromise security.

The web app is kept small enough for a final project: login, WebSocket relay, database storage, and chat UI are included so the crypto can be tested in a real workflow. Most of the work is in the encryption protocol, key handling, ratchet state, threat model, and experiments.

## Team

Institution: Ho Chi Minh City University of Technology and Engineering (HCM-UTE)

| Name | GitHub | Primary Area |
|---|---|---|
| Ly Van Huu Hoa | [@hoalvh](https://github.com/hoalvh) | Application security, authentication, backend relay, Security Lab backend |
| Le Quang Minh | [@hnhat1234](https://github.com/hnhat1234) | E2EE protocol, key schedule, ratchet, protocol testing |
| Tran Quoc Truong | [@siberlly](https://github.com/siberlly) | Frontend security UX, client state, evaluation UI |

Team responsibilities and execution plan: [docs/00-project/team-and-execution-plan.md](docs/00-project/team-and-execution-plan.md)

## Project Focus

This project is a secure chat prototype, not a complete messaging product.

Main focus:

- End-to-end encryption.
- Device identity and public key binding.
- Per-message key derivation.
- Symmetric ratchet.
- DH ratchet.
- Forward secrecy.
- Post-compromise security.
- Replay and tamper resistance.
- Key-substitution warning.
- Security experiments and benchmark evidence.

Supporting features such as login, database storage, WebSocket relay, and chat UI are implemented only to the level needed for a working demo.

Scope boundaries and non-goals: [docs/00-project/project-scope.md](docs/00-project/project-scope.md)

## Core Security Goals

| Goal | Project Meaning |
|---|---|
| Authentication is separate from encryption | JWT authenticates users/devices to the server, but does not encrypt or decrypt messages |
| Ciphertext-only server | The backend stores public key material, routing metadata, and ciphertext, but never plaintext messages or private keys |
| Per-message secrecy | Each message is encrypted with a fresh message key derived from ratchet state |
| Forward secrecy | After key erasure, current state should not decrypt old messages |
| Post-compromise security | After temporary client-state compromise, a later DH ratchet should recover future message confidentiality |
| Security UX | Safety numbers, key-change warnings, replay/tamper alerts, and recovery status are visible in the UI |

## MVP Features

- Username/password registration and login.
- Password hashing with Argon2id.
- Short-lived JWT access tokens and refresh-token sessions.
- WebSocket authentication.
- Simple device registration.
- Client-side identity key and signed prekey.
- One-to-one end-to-end encrypted chat.
- Symmetric ratchet and DH ratchet.
- Safety number or key fingerprint display.
- Key-change warning.
- Security Lab for attack simulations and metrics.

Out of scope for the MVP:

- Full multi-device synchronization.
- Group messaging with MLS.
- Key transparency.
- Encrypted backup and recovery keys.
- Production deployment hardening.
- Formal verification with Tamarin or ProVerif.

## Architecture

```text
+-------------------+        REST/JWT         +----------------------+
| Alice Web Client  | <---------------------> | Auth + API Server    |
| - JWT in memory   |                         | - Argon2id password  |
| - Private keys    |        WebSocket        | - JWT verification   |
| - Ratchet state   | <---------------------> | - Key directory      |
| - E2EE crypto     |                         | - Ciphertext relay   |
+-------------------+                         +----------------------+
          |                                             ^
          | E2EE ciphertext only                        |
          v                                             |
+-------------------+                         +----------------------+
| Bob Web Client    |                         | PostgreSQL + Prisma  |
| - Private keys    |                         | - users/devices      |
| - Ratchet state   |                         | - public keys only   |
| - Decrypt locally |                         | - encrypted messages |
+-------------------+                         +----------------------+

+-------------------+
| Security Lab UI   |
| - server dump     |
| - stolen JWT sim  |
| - replay/tamper   |
| - PCS timeline    |
+-------------------+
```

The repository uses a modular layered monorepo rather than classic MVC. The cryptographic protocol is separated from both the UI and backend so it can be tested, reviewed, and explained independently.

Architecture and stack notes: [docs/00-project/technology-decisions.md](docs/00-project/technology-decisions.md)

## Technology Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | React + TypeScript + Vite | Chat UI, login, device setup, Security Lab |
| Styling | Tailwind CSS | Consistent MVP UI and security-state components |
| Client storage | IndexedDB / Dexie | Local private keys, device metadata, ratchet state |
| Backend | Node.js + TypeScript + Fastify | Auth, device/key APIs, message relay, lab endpoints |
| Realtime | WebSocket | Encrypted packet relay |
| Database | PostgreSQL + Prisma | Users, devices, public key bundles, ciphertext messages |
| Auth | Argon2id + JWT + refresh cookie | Login and session management |
| Crypto | libsodium-wrappers-sumo + @noble/hashes | X25519, Ed25519, XChaCha20-Poly1305, HKDF/SHA-256 |
| Testing | Vitest + Playwright | Protocol unit tests and browser security-flow tests |
| Benchmarking | k6 / autocannon | Latency, throughput, and overhead measurements |
| Local environment | Docker Compose | Reproducible local database setup |

## Repository Layout

```text
secure-web-chat/
├─ README.md
├─ docker-compose.yml
├─ .env.example
├─ docs/
│  ├─ README.md
│  ├─ 00-project/
│  ├─ 01-design/
│  ├─ 02-evaluation/
│  └─ proposal/
├─ apps/
│  ├─ web/
│  └─ server/
├─ packages/
│  └─ protocol/
├─ prisma/
├─ experiments/
├─ benchmarks/
├─ scripts/
├─ report/
└─ presentation/
```

| Directory | Purpose |
|---|---|
| `docs/` | Project docs, design decisions, protocol notes, evaluation plan |
| `apps/web/` | React frontend and browser-side security UX |
| `apps/server/` | Fastify backend, auth, key directory, ciphertext relay |
| `packages/protocol/` | Shared protocol types, packet validation, key schedule helpers |
| `prisma/` | Database schema and migrations |
| `experiments/` | Attack simulations and reproducible security experiments |
| `benchmarks/` | Performance scripts and benchmark outputs |
| `report/` | Final written report material |
| `presentation/` | Slides, demo script, and presentation assets |

## Documentation

| Document | Purpose |
|---|---|
| [docs/README.md](docs/README.md) | Documentation index |
| [Team and Execution Plan](docs/00-project/team-and-execution-plan.md) | Roles, ownership, milestones, branch workflow |
| [Project Scope and Non-Goals](docs/00-project/project-scope.md) | MVP depth, non-goals, database scope, algorithm scope |
| [Technology Decisions](docs/00-project/technology-decisions.md) | Stack choices, alternatives, trade-offs |
| [Repository Hygiene](docs/00-project/repository-hygiene.md) | GitHub setup, `.env` rules, secret-handling notes |
| [Threat Model](docs/01-design/threat-model.md) | Assets, trust boundaries, attacker scenarios |
| [Authentication and JWT](docs/01-design/authentication-and-jwt.md) | Auth flow, JWT, refresh session, WebSocket auth |
| [E2EE Protocol Design](docs/01-design/e2ee-protocol-design.md) | Packet format and encrypted messaging protocol |
| [Key Schedule and Ratchet](docs/01-design/key-schedule-and-ratchet.md) | Root keys, chain keys, message keys, DH ratchet |
| [Experiment Plan](docs/02-evaluation/experiment-plan.md) | Server compromise, stolen JWT, replay, tamper, FS, PCS |

## Evaluation Plan

The Security Lab is the main demonstration and evaluation interface.

| Scenario | Expected Evidence |
|---|---|
| Server compromise | Server database contains ciphertext only |
| Stolen JWT | JWT can access server APIs temporarily but cannot decrypt messages |
| Replay attack | Replayed packet is rejected |
| Tamper attack | Modified header/ciphertext fails AEAD verification |
| Key substitution | UI displays key-change or unverified-key warning |
| Forward secrecy | Past messages remain protected after current-state exposure |
| Post-compromise security | Future messages recover after a DH ratchet event |

Performance measurements include login latency, JWT verification time, WebSocket auth latency, encrypt/decrypt time, DH rekey latency, ciphertext overhead, and relay throughput.

## Security Constraints

- Do not implement low-level cryptographic primitives manually when reviewed libraries are available.
- Do not store private keys or ratchet state on the server.
- Do not store long-lived access tokens in `localStorage`.
- Do not pass JWTs through WebSocket URL query strings.
- Use authenticated encryption with stable associated data for encrypted message packets.
- Keep experiment results reproducible and separate from source code.

## Repository Safety

Commit `.env.example`, but never commit `.env`, private keys, real secrets, local database files, logs, or generated dependency/build artifacts.

Repository hygiene details: [docs/00-project/repository-hygiene.md](docs/00-project/repository-hygiene.md)
