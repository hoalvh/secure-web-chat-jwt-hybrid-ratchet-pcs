# Team and Execution Plan

This document defines the project team, role ownership, collaboration boundaries, milestones, and completion criteria.

## 1. Institution

Ho Chi Minh City University of Technology and Engineering (HCM-UTE)

## 2. Team Members

| No. | Name | GitHub | Primary Role |
|---:|---|---|---|
| 1 | Ly Van Huu Hoa | [@hoalvh](https://github.com/hoalvh) | Application Security, Authentication, Backend Relay, Security Lab Backend |
| 2 | Le Quang Minh | [@hnhat1234](https://github.com/hnhat1234) | Cryptographic Protocol, Key Schedule, Ratchet, Protocol Testing |
| 3 | Tran Quoc Truong | [@siberlly](https://github.com/siberlly) | Frontend Security UX, Client State, Evaluation UI |

## 3. Author Line

For English proposal/report:

```text
Authors: Ly Van Huu Hoa (@hoalvh), Le Quang Minh (@hnhat1234), Tran Quoc Truong (@siberlly)
Institution: Ho Chi Minh City University of Technology and Engineering (HCM-UTE)
```

For repository metadata:

```text
Maintainers: @hoalvh, @hnhat1234, @siberlly
```

## 4. Role Ownership

| Workstream | Primary Owner | Scope |
|---|---|---|
| Application Security and Security Lab Backend | Ly Van Huu Hoa | Auth API, JWT, refresh sessions, device/key APIs, WebSocket auth, ciphertext relay, lab attack endpoints |
| Cryptographic Protocol and Ratchet Core | Le Quang Minh | E2EE packet format, key schedule, AEAD, symmetric ratchet, DH ratchet, replay rules, protocol tests |
| Frontend Security UX and Evaluation UI | Tran Quoc Truong | React UI, device setup, chat UI, client storage integration, security states, Security Lab dashboard |

## 5. Responsibility Matrix

| Area | Ly Van Huu Hoa | Le Quang Minh | Tran Quoc Truong |
|---|---:|---:|---:|
| Repository hygiene and branch rules | Lead | Review | Review |
| Backend foundation | Lead | Review | Integrate |
| Register/login/JWT/refresh | Lead | Review | Integrate |
| WebSocket authentication | Lead | Review | Integrate |
| Database schema | Lead | Review | Review |
| Device public key API | Lead | Review | Integrate |
| E2EE packet format | Review | Lead | Integrate |
| Key schedule and ratchet | Review | Lead | Integrate |
| AEAD encryption/decryption | Review | Lead | Integrate |
| Replay/tamper protocol rules | Integrate | Lead | Integrate |
| Client key storage | Review | Integrate | Lead |
| Register/login UI | Integrate | Review | Lead |
| Device setup UI | Integrate | Integrate | Lead |
| Chat UI | Integrate | Integrate | Lead |
| Safety number UI | Review | Review | Lead |
| Key-change warning UI | Review | Review | Lead |
| Security Lab backend | Lead | Integrate | Integrate |
| Security Lab frontend | Integrate | Review | Lead |
| Security experiments | Lead attack cases | Lead crypto cases | Lead UI evidence |
| Benchmarks | Auth/server metrics | Crypto metrics | UI/E2E evidence |
| Final report sections | Threat model, auth, lab backend | Protocol, key schedule, PCS | UI/UX, screenshots, evaluation UI |
| Final presentation sections | Attack demo | Crypto explanation | Product/security UX demo |

## 6. Integration Contracts

### 6.1. Auth and Frontend Contract

Owner: Application Security workstream  
Integrator: Frontend Security UX workstream

Required endpoints:

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /me
```

Required behavior:

- Passwords are stored only as Argon2id hashes.
- Access JWTs are short-lived.
- Refresh tokens are stored as HttpOnly cookies.
- Auth errors are generic.
- The frontend does not store long-lived tokens in localStorage.

### 6.2. Protocol and Frontend Contract

Owner: Cryptographic Protocol workstream  
Integrator: Frontend Security UX workstream

Required client-facing functions:

```text
generateDeviceIdentity()
createPublicKeyBundle()
verifyPublicKeyBundle()
deriveSafetyNumber()
initializeSession()
encryptMessage()
decryptMessage()
advanceSymmetricRatchet()
advanceDhRatchet()
```

Required protocol error codes:

```text
DECRYPT_FAILED
REPLAY_DETECTED
MESSAGE_TOO_OLD
UNSUPPORTED_VERSION
KEY_CHANGED
INVALID_PREKEY_SIGNATURE
```

### 6.3. Backend and Protocol Contract

Owner: Application Security workstream  
Reviewer: Cryptographic Protocol workstream

Required behavior:

- The server validates outer encrypted packet metadata.
- The server never decrypts message ciphertext.
- The server stores public keys, ciphertext, and routing metadata only.
- Lab endpoints simulate attacks without requiring plaintext access.

## 7. Member Task Tracks

### 7.1. Ly Van Huu Hoa

Primary folders:

```text
apps/server/
apps/server/src/auth/
apps/server/src/devices/
apps/server/src/keys/
apps/server/src/messages/
apps/server/src/websocket/
apps/server/src/lab/
prisma/
experiments/server_compromise/
experiments/jwt_theft/
experiments/replay_tamper/
experiments/key_substitution/
```

Main deliverables:

- Fastify backend foundation.
- Prisma schema and migrations.
- Register/login APIs.
- Argon2id password hashing.
- JWT access-token verification.
- Refresh-token session management.
- Device and public key APIs.
- WebSocket ciphertext relay.
- Security Lab backend endpoints.

Validation checklist:

- No plaintext password storage.
- No plaintext message storage.
- No private key accepted by the backend.
- Expired or invalid JWTs are rejected.
- Refresh tokens are stored as hashes.
- WebSocket messages require authentication.
- Lab endpoints return structured, reproducible results.

### 7.2. Le Quang Minh

Primary folders:

```text
packages/protocol/
packages/protocol/src/
packages/protocol/tests/
apps/web/src/crypto/
experiments/forward_secrecy/
experiments/post_compromise_security/
```

Main deliverables:

- Shared protocol constants and packet types.
- Device identity key generation.
- Signed prekey generation and verification.
- Public key bundle format.
- Safety number derivation.
- Initial session setup.
- Symmetric ratchet.
- DH ratchet.
- AEAD message encryption/decryption.
- Replay protection rules.
- Protocol test vectors.

Validation checklist:

- No custom low-level cryptographic primitive implementation.
- Private keys remain client-side.
- Message keys are unique per message.
- Associated data covers important packet headers.
- Replay and tamper failures return explicit error codes.
- Old keys are removed from application state where practical.
- FS and PCS behavior is covered by tests or experiments.

### 7.3. Tran Quoc Truong

Primary folders:

```text
apps/web/
apps/web/src/auth/
apps/web/src/session/
apps/web/src/storage/
apps/web/src/chat/
apps/web/src/websocket/
apps/web/src/lab/
apps/web/src/shared/
apps/web/tests/
```

Main deliverables:

- React + TypeScript + Vite frontend foundation.
- Tailwind UI setup.
- Register/login UI.
- Device setup UI.
- IndexedDB/Dexie client state integration.
- One-to-one chat UI.
- WebSocket client integration.
- Safety number modal.
- Key-change warning.
- Replay/tamper/decryption failure states.
- Security Lab dashboard.
- Screenshot-ready evaluation views.

Validation checklist:

- UI does not expose raw tokens.
- Private keys are not sent to the backend.
- Security states are visible with text, not color only.
- Key-change and decrypt-failure warnings are prominent.
- Lab results are readable and suitable for report screenshots.
- UI works after page reload.
- API and protocol contract changes are reflected in documentation.

## 8. Milestones

### Milestone 1: Project Foundation

| Deliverable | Owner |
|---|---|
| Backend skeleton | Ly Van Huu Hoa |
| Frontend skeleton | Tran Quoc Truong |
| Protocol package skeleton | Le Quang Minh |
| Prisma schema draft | Ly Van Huu Hoa |

### Milestone 2: Authentication and Device Setup

| Deliverable | Owner |
|---|---|
| Argon2id register/login | Ly Van Huu Hoa |
| JWT and refresh flow | Ly Van Huu Hoa |
| Device key generation | Le Quang Minh |
| Device setup UI | Tran Quoc Truong |
| Public key bundle API integration | Shared |

### Milestone 3: Encrypted One-to-One Chat

| Deliverable | Owner |
|---|---|
| E2EE packet format | Le Quang Minh |
| Initial session setup | Le Quang Minh |
| Symmetric ratchet | Le Quang Minh |
| WebSocket ciphertext relay | Ly Van Huu Hoa |
| Chat UI integration | Tran Quoc Truong |

### Milestone 4: DH Ratchet and Security UX

| Deliverable | Owner |
|---|---|
| DH ratchet | Le Quang Minh |
| Replay/tamper protocol rules | Le Quang Minh |
| Safety number UI | Tran Quoc Truong |
| Key-change warning UI | Tran Quoc Truong |
| Lab attack hooks | Ly Van Huu Hoa |

### Milestone 5: Security Lab and Evaluation

| Deliverable | Owner |
|---|---|
| Server compromise demo | Ly Van Huu Hoa |
| Stolen JWT demo | Ly Van Huu Hoa |
| Replay/tamper demo | Shared |
| Forward secrecy experiment | Le Quang Minh |
| PCS experiment | Le Quang Minh |
| Lab dashboard and screenshots | Tran Quoc Truong |
| Benchmark/result tables | Shared |

## 9. Branch Workflow

All implementation work must happen on feature branches. The `main` branch is reserved for reviewed, demo-ready work.

Branch naming:

```text
feature/<area>-<short-name>
docs/<short-name>
experiment/<scenario>
fix/<short-name>
```

Pull request requirements:

- Include a short description.
- Include testing or manual verification notes.
- Reference updated documentation when behavior changes.
- Request review from the owner of the affected workstream.
- Do not merge directly to `main` without review.

## 10. Definition of Done

A task is complete only when:

- Work is committed on a feature branch.
- The implementation matches the relevant design document.
- Sensitive values are not committed.
- Tests or manual verification notes are included.
- Affected documentation is updated.
- At least one teammate reviews the pull request.

