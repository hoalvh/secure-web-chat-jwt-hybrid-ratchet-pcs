# Team and Execution Plan

This document defines the project team, role ownership, collaboration boundaries, milestones, and completion criteria. It is aligned with the current FastAPI + browser Web Crypto MVP.

## 1. Institution

Ho Chi Minh City University of Technology and Engineering (HCM-UTE)

## 2. Team Members

| No. | Name | GitHub | Primary Role |
|---:|---|---|---|
| 1 | Ly Van Huu Hoa | [@hoalvh](https://github.com/hoalvh) | Application Security, Authentication, Backend Relay, Security Lab Backend |
| 2 | Le Quang Minh | [@hnhat1234](https://github.com/hnhat1234) | Cryptographic Protocol, Key Schedule, Ratchet, Protocol Testing |
| 3 | Tran Quoc Truong | [@siberlly](https://github.com/siberlly) | Frontend Security UX, Client State, Admin/Demo UI |

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
| Application Security and Security Lab Backend | Ly Van Huu Hoa | FastAPI auth, JWT, refresh sessions, device/key APIs, WebSocket auth, ciphertext relay, lab endpoints |
| Cryptographic Protocol and Ratchet Core | Le Quang Minh | Web Crypto E2EE packet format, key schedule, AEAD, simplified ratchet, PCS explanation, protocol tests |
| Frontend Security UX and Admin/Demo UI | Tran Quoc Truong | Browser UI, IndexedDB client state, chat UX, key inspector, admin dashboard, screenshots |

## 5. Responsibility Matrix

| Area | Ly Van Huu Hoa | Le Quang Minh | Tran Quoc Truong |
|---|---:|---:|---:|
| Repository hygiene and branch rules | Lead | Review | Review |
| FastAPI backend foundation | Lead | Review | Integrate |
| Register/login/JWT/refresh | Lead | Review | Integrate |
| WebSocket authentication | Lead | Review | Integrate |
| Database store boundaries (SQLAlchemy/Alembic) | Lead | Review | Review |
| Device public key API | Lead | Review | Integrate |
| E2EE packet format | Review | Lead | Integrate |
| Key schedule and ratchet concept | Review | Lead | Integrate |
| AES-GCM encryption/decryption | Review | Lead | Integrate |
| Replay/tamper protocol rules | Integrate | Lead | Integrate |
| IndexedDB client key storage | Review | Integrate | Lead |
| Register/login UI | Integrate | Review | Lead |
| Chat UI | Integrate | Integrate | Lead |
| Fingerprint/key-change UI | Review | Review | Lead |
| Security Lab backend | Lead | Integrate | Integrate |
| Admin/evidence frontend | Integrate | Review | Lead |
| Security experiments | Lead attack cases | Lead crypto cases | Lead UI evidence |
| Benchmarks | Auth/server metrics | Crypto metrics | UI/evidence metrics |
| Final report sections | Threat model, auth, lab backend | Protocol, key schedule, PCS | UI/UX, screenshots, evaluation UI |
| Final presentation sections | Attack demo | Crypto explanation | Product/security UX demo |

## 6. Integration Contracts

### 6.1. Auth and Frontend Contract

Required endpoints:

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /me
```

Required behavior:

- Passwords are stored only as password hashes.
- Access JWTs are short-lived.
- Refresh tokens are stored as HttpOnly cookies.
- Auth errors are generic.
- The frontend does not store long-lived tokens in `localStorage`.

### 6.2. Device and Protocol Contract

Required behavior:

- Browser generates device private key.
- Browser sends only public JWK and fingerprint to the server.
- Backend rejects JWKs containing private field `d`.
- Contact key lookup returns public key bundle only.
- Fingerprint/key-change state is visible in the UI.

### 6.3. Backend and Message Contract

Required behavior:

- The server validates outer encrypted packet metadata.
- The server never decrypts message ciphertext.
- The server rejects packets containing plaintext.
- The server stores public keys, ciphertext, and routing metadata only.
- Lab endpoints simulate attacks without requiring plaintext access.

## 7. Member Task Tracks

### 7.1. Ly Van Huu Hoa

Primary folders:

```text
apps/server/
apps/server/tests/
docs/02-evaluation/
```

Main deliverables:

- FastAPI backend foundation.
- Register/login APIs.
- Argon2id password hashing.
- JWT access-token verification.
- Refresh-token session management.
- Device and public key APIs.
- WebSocket ciphertext notification.
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
apps/web/src/app.js
docs/01-design/
docs/02-evaluation/
```

Main deliverables:

- E2EE packet format.
- Device key generation flow.
- Public key bundle format.
- Fingerprint derivation.
- ECDH/HKDF/AES-GCM composition.
- Simplified symmetric ratchet.
- PCS/DH rekey explanation and metrics.
- Replay protection rules.
- Protocol test targets or vectors.

Validation checklist:

- No custom low-level cryptographic primitive implementation.
- Private keys remain client-side.
- Message keys are unique per message.
- Associated data covers important packet headers.
- Replay and tamper failures are visible.
- FS and PCS limitations are documented honestly.

### 7.3. Tran Quoc Truong

Primary folders:

```text
apps/web/
apps/web/src/
docs/01-design/security-ux.md
docs/02-evaluation/
```

Main deliverables:

- Vanilla JS frontend styled with Tabler/Bootstrap (CDN).
- Register/login UI.
- Contact list and manual contact opening.
- IndexedDB client state integration.
- One-to-one chat UI.
- WebSocket client integration.
- Fingerprint display.
- Key-change warning.
- Replay/tamper/decryption failure states.
- User chat key/fingerprint inspector.
- Admin dashboard for server-side hashes/ciphertext/public keys.
- Screenshot-ready evaluation views.

Validation checklist:

- UI does not expose raw tokens.
- Private keys are not sent to the backend.
- Security states are visible with text, not color only.
- Key-change and decrypt-failure warnings are prominent.
- Admin/lab evidence is readable and suitable for report screenshots.
- UI works after page reload.
- API and protocol contract changes are reflected in documentation.

## 8. Milestones

### Milestone 1: Project Foundation

| Deliverable | Owner |
|---|---|
| FastAPI backend skeleton | Ly Van Huu Hoa |
| Browser frontend skeleton | Tran Quoc Truong |
| Protocol documentation skeleton | Le Quang Minh |
| Repository hygiene docs | Shared |

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
| ECDH/HKDF/AES-GCM flow | Le Quang Minh |
| Symmetric ratchet concept | Le Quang Minh |
| Ciphertext relay | Ly Van Huu Hoa |
| Chat UI integration | Tran Quoc Truong |

### Milestone 4: Security UX

| Deliverable | Owner |
|---|---|
| Replay/tamper protocol rules | Le Quang Minh |
| Fingerprint display | Tran Quoc Truong |
| Key-change warning UI | Tran Quoc Truong |
| Lab attack hooks | Ly Van Huu Hoa |

### Milestone 5: Security Lab and Evaluation

| Deliverable | Owner |
|---|---|
| Server compromise demo | Ly Van Huu Hoa |
| Stolen JWT demo | Ly Van Huu Hoa |
| Replay/tamper demo | Shared |
| Forward secrecy explanation | Le Quang Minh |
| PCS metric | Le Quang Minh |
| Admin dashboard and screenshots | Tran Quoc Truong |
| Benchmark/result tables | Shared |

## 9. Branch Workflow

All implementation work should happen on feature branches. The `main` branch is reserved for reviewed, demo-ready work.

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

- The implementation matches the relevant design document.
- Sensitive values are not committed.
- Tests or manual verification notes are included.
- Affected documentation is updated.
- At least one teammate reviews the pull request when using PR workflow.
