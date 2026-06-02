# Technology Decisions

This document records the main technology choices for the project and the trade-offs behind them.

## 1. Decision Principles

The stack is chosen using five principles:

- **Cryptographic clarity:** authentication, transport security, and end-to-end encryption must remain separate concepts.
- **Testability:** protocol logic must be testable without running the full web application.
- **Reproducibility:** experiments and benchmarks should run from documented scripts.
- **Course fit:** the implementation should make cryptographic behavior visible enough for explanation and testing.
- **Controlled scope:** the project should stay within a three-week final-project workload.

Detailed scope boundaries are defined in [`project-scope.md`](project-scope.md).

## 2. Project Scope

This is a **Cryptography course project**, not a general-purpose chat product. The stack is chosen so the team can build and test the encrypted messaging flow without spending most of the time on product features.

The project should go deep on:

- End-to-end encryption.
- Device identity and key binding.
- Signed prekeys.
- Symmetric ratchet.
- DH ratchet.
- Forward secrecy.
- Post-compromise security.
- Replay and tamper resistance.
- Key substitution detection.
- Security benchmarks and experiment evidence.

Other application features are kept at MVP level:

- Login/register.
- JWT session management.
- Device setup.
- One-to-one chat.
- Contact selection.
- Message relay.
- Relational database schema with practical constraints and indexes.
- Basic local persistence.
- Security-state UI.

These features give the protocol a realistic context. They should stay simple unless a change is needed for the security demo.

Possible extensions after the MVP:

| Current MVP feature | Future extension path |
|---|---|
| One-device-per-user or simple device model | Full multi-device support with per-device sessions |
| One-to-one chat | Group messaging or MLS-based group encryption |
| Basic JWT login | MFA, OAuth, account recovery, session dashboard |
| Local IndexedDB key storage | Encrypted backup and recovery-key flow |
| Manual safety number verification | Key transparency or audit log |
| Local Docker Compose setup | Production deployment with observability and hardened secrets |
| Basic PostgreSQL schema and indexes | Partitioning, sharding, replication, and advanced query tuning |

The main implementation and report effort should stay on encryption design, threat model, tests, and experiment results.

## 3. Architecture Decision

### Chosen Approach

The project uses a **modular layered monorepo**:

- `apps/web/` for browser UI, local keys, local ratchet state, and client-side cryptography.
- `apps/server/` for login, JWT verification, device/key directory, message relay, and lab controls.
- `packages/protocol/` for shared packet formats, validation, canonical encoding, and protocol constants.
- `docs/`, `experiments/`, and `benchmarks/` for design evidence and grading artifacts.

### MVC Note

Classic MVC is not the best fit here because the difficult part is protocol state: root keys, chain keys, message counters, skipped-message keys, associated data, replay windows, and compromise recovery.

If the project is organized around controllers and models only, crypto logic can drift into the backend or UI. Keeping a separate protocol package makes it easier to test.

### Folder Structure Fit

The current folder structure already matches this choice:

- Application boundaries are explicit through `apps/web/` and `apps/server/`.
- Shared protocol code has its own package instead of being duplicated.
- Experiments and benchmarks have their own folders.
- Documentation lives next to implementation, so each design claim can later be linked to a test or experiment.

## 4. Frontend Stack

### React

React is chosen because the frontend has several stateful views: login/register, device setup, contact list, conversation, safety number modal, key-change warning, and Security Lab dashboard.

React fits this because:

- UI can be split into small components that map naturally to security states.
- State changes such as `unverified`, `key changed`, `tamper detected`, and `recovered after rekey` can be represented clearly.
- The team can build an interactive lab without introducing a heavier full-stack framework.

Alternatives considered:

| Alternative | Why not chosen |
|---|---|
| Vanilla JavaScript | Too much manual state handling for chat and lab UI |
| Next.js | Useful for full-stack SSR apps, but unnecessary because this project does not need SEO or server-rendered pages |
| Vue/Svelte | Also valid, but React has broad team familiarity and testing ecosystem support |

### TypeScript

TypeScript is chosen across frontend, backend, and shared protocol code.

Reasons:

- Message packets, JWT claims, device IDs, counters, and protocol versions should have explicit types.
- Shared types reduce mismatch between client packets and server relay validation.
- Cryptographic code benefits from stronger compile-time checks around byte arrays, encoded strings, and packet structures.

TypeScript does not prove protocol security, but it reduces ordinary implementation mistakes that would weaken the demo.

### Vite

Vite is chosen for the frontend build/dev environment.

Reasons:

- It supports React and TypeScript with a small configuration surface.
- Fast local development helps the team iterate on UI and Security Lab screens.
- It avoids the extra routing and deployment assumptions of a larger full-stack framework.

Trade-off: Vite is a frontend tool only, so the backend remains a separate Fastify app. This fits the project because the server is an auth/key/message relay, not a page-rendering server.

### Tailwind CSS

Tailwind CSS is chosen because the project needs clear, consistent security-state UI more than custom visual branding.

Reasons:

- Security badges, warning panels, lab controls, and chat states can be styled consistently.
- Utility classes reduce time spent designing a CSS architecture.
- It reduces time spent on CSS structure.

Trade-off: Tailwind classes can become noisy in large components. The mitigation is to extract repeated UI patterns into components such as `SecurityBadge`, `KeyChangeWarning`, and `LabMetricCard`.

### IndexedDB and Dexie

IndexedDB is chosen because the browser client must persist local cryptographic state. Dexie is used as a thin wrapper to make IndexedDB safer and easier to use from TypeScript.

Stored locally:

- Device ID.
- Private identity key.
- Signed prekey private key.
- Current ratchet state.
- Skipped message keys if out-of-order handling is implemented.
- Safety number verification status.

Why not `localStorage`:

- It is synchronous and too limited for structured cryptographic state.
- It encourages simple string dumps of sensitive data.
- It is easier to misuse for tokens and long-lived secrets.

Important limitation: IndexedDB does not make browser malware, XSS, or malicious extensions safe. The project must still document XSS as a serious threat.

## 5. Backend Stack

### Node.js and TypeScript

Node.js with TypeScript is chosen to keep one language across the frontend, backend, and shared protocol package.

Reasons:

- Shared packet types and validation logic can be reused.
- Team members only need one main runtime and package ecosystem.
- WebSocket and JSON API implementation is straightforward.

Trade-off: Node.js is not chosen for heavy CPU-bound cryptography. Server-side crypto is limited to password hashing, token signing/verification, and public key validation. End-to-end message encryption remains client-side.

### Fastify

Fastify is chosen as the backend framework.

Reasons:

- It is lightweight and has enough structure for the API.
- Route-level schemas match the need to validate auth, device, key, and message-relay inputs.
- It avoids the boilerplate of larger opinionated frameworks.
- It works well with TypeScript and a modular folder structure.

Alternatives considered:

| Alternative | Why not chosen |
|---|---|
| Express | Simple, but less structured around route schemas by default |
| NestJS | Strong architecture, but heavier than needed for this project |
| Next.js API routes | Couples backend to frontend framework and weakens the clear client/server trust boundary |

### PostgreSQL

PostgreSQL is chosen as the database.

Reasons:

- The domain is relational: users, devices, refresh sessions, public key bundles, conversations, and messages.
- Constraints and indexes are useful for unique usernames, device ownership, message lookup, and replay-related metadata.
- It can store structured metadata while keeping ciphertext as opaque bytes/text.

Why not MongoDB:

- Flexible documents are not the main need here.
- Strong relational constraints are more valuable for auth and device ownership.

Why not SQLite as the main database:

- SQLite is fine for a tiny local demo, but PostgreSQL is closer to a realistic web deployment and works well with Docker Compose.

### Prisma

Prisma is chosen for database access and migrations.

Reasons:

- Type-safe database access reduces mistakes in auth/session/device queries.
- Migrations make the schema reproducible for teammates and grading.
- The Prisma schema gives the report a clean way to show the stored data model.

Trade-off: Prisma adds generated code and an ORM abstraction. If the project later focuses on low-level database tuning, raw SQL may be better. For this MVP, Prisma keeps the schema and migrations easy to reproduce.

## 6. Authentication Libraries

### Argon2id

Argon2id is chosen for password hashing.

Reasons:

- Passwords must never be stored as plaintext or reversible encryption.
- Argon2id is a modern password hashing choice with memory-hard behavior.
- It is more suitable for a new project than legacy password hashing choices.

Trade-off: Argon2id parameters must be tuned so login is slow enough to resist guessing but still usable in the demo environment. The chosen parameters should be benchmarked and documented.

### JWT

JWT is chosen for short-lived access tokens.

Reasons:

- The server can verify access without querying a session table on every request.
- JWT claims can include `sub`, `device_id`, `session_id`, `iat`, `exp`, and `jti`.
- It works cleanly for REST and WebSocket authentication when sent through an auth frame.

Important boundary:

- JWT authenticates a user/device to the server.
- JWT does not encrypt messages.
- JWT does not prove that a public key belongs to the right human.
- JWT compromise should not reveal plaintext without local device keys.

### HttpOnly Refresh Cookie

Refresh tokens are stored as opaque random values in HttpOnly cookies and hashed in the database.

Reasons:

- Access JWTs can be short-lived.
- Refresh sessions can be revoked on logout.
- Hashing refresh tokens limits damage if the database is inspected.
- HttpOnly cookies reduce direct JavaScript access compared with storing long-lived tokens in localStorage.

Trade-off: cookies require CSRF-aware design. The project should use SameSite settings and restrict refresh endpoints.

### `jose`

`jose` is chosen for JWT/JWS handling.

Reasons:

- JWT signing and verification should not be implemented manually.
- The library supports standard JOSE/JWT concepts.
- It works across modern JavaScript runtimes, which fits a TypeScript project.

Planned algorithm: RS256 for access-token signing. This keeps account-session tokens separate from Ed25519 device identity keys and makes server-side key rotation easier to explain in the report.

## 7. Cryptography Libraries

### libsodium-wrappers-sumo

`libsodium-wrappers-sumo` is chosen for high-level cryptographic primitives.

Used for:

- X25519 key agreement.
- Ed25519 signatures.
- XChaCha20-Poly1305 authenticated encryption.
- Secure random bytes.

Reasons:

- The project must not implement low-level primitives manually.
- Libsodium provides well-known high-level APIs for modern cryptographic operations.
- XChaCha20-Poly1305 is convenient for message encryption because it uses a large nonce space and AEAD authentication.
- X25519 and Ed25519 match the Signal-inspired design.

Trade-off: the browser build includes WebAssembly/JavaScript wrapper overhead. For this MVP, crypto correctness matters more than minimal bundle size.

### @noble/hashes

`@noble/hashes` is chosen for hash and KDF helpers such as SHA-256 and HKDF when not using an equivalent libsodium API.

Reasons:

- HKDF and SHA-256 are needed for root keys, chain keys, message keys, and safety-number fingerprints.
- A small focused hashing library keeps the key schedule explicit and testable.
- It works naturally in TypeScript.

Rule: hash/KDF usage must be centralized in `packages/protocol/` or `apps/web/src/crypto/`, not scattered across UI components.

### Browser Web Crypto Note

Browser Web Crypto is useful, but it is not selected as the primary crypto layer for this project.

Reasons:

- The project wants a consistent API for X25519, Ed25519, XChaCha20-Poly1305, and related helpers.
- XChaCha20-Poly1305 is not the normal Web Crypto AEAD option.
- Libsodium keeps the algorithm set consistent for the Signal-inspired protocol.

Web Crypto may still be used for random generation or supporting utilities if it does not split the protocol into inconsistent implementations.

## 8. Realtime Communication

### WebSocket

WebSocket is chosen for realtime encrypted message relay.

Reasons:

- Chat needs bidirectional communication.
- The server should relay ciphertext packets without understanding plaintext.
- A direct WebSocket protocol makes packet framing, authentication frames, and replay experiments easier to explain.

Why not Socket.IO:

- Socket.IO is convenient, but it adds an extra abstraction and fallback behavior that is not needed for the MVP.
- The project benefits from showing exactly what encrypted packet is sent over the wire.

Why not polling:

- Polling is simpler but less realistic for chat and makes latency benchmarks less meaningful.

## 9. Testing and Benchmarking

### Vitest

Vitest is chosen for unit tests.

Test targets:

- Packet validation.
- Canonical encoding.
- HKDF output consistency.
- Ratchet step behavior.
- Replay counter checks.
- JWT claim validation helpers.

Reason: it fits the Vite/TypeScript ecosystem and allows fast feedback for protocol helper functions.

### Playwright

Playwright is chosen for end-to-end browser tests.

Test targets:

- Login/register flow.
- Device setup.
- Sending and receiving encrypted messages.
- Key-change warning display.
- Replay/tamper detection UI.
- Security Lab demo flow.

Reason: the project needs proof that security UX is not just documentation. Browser automation can verify that warnings and lab states appear as intended.

### k6

k6 is chosen for scripted load/performance tests.

Use cases:

- Login endpoint latency.
- JWT refresh endpoint behavior.
- Message relay under multiple simulated users.
- WebSocket connection behavior if included in the benchmark plan.

### autocannon

autocannon is chosen for focused local HTTP benchmarking.

Use cases:

- Fastify route throughput.
- JWT verification endpoint overhead.
- API latency before and after validation middleware.

Why both k6 and autocannon:

- `autocannon` is convenient for quick local API measurements.
- `k6` is better for scripted scenarios and result reporting.

## 10. Local Environment

### Docker Compose

Docker Compose is chosen for the local environment.

Reasons:

- PostgreSQL can be started consistently across team machines.
- The setup is easy to reset for demos.
- It documents runtime dependencies in one file.

Not every service needs to be containerized during development. The MVP can run Node/Vite directly on the host while PostgreSQL runs in Docker.

## 11. Decision Summary

| Decision | Main reason | Main trade-off |
|---|---|---|
| React + TypeScript + Vite | Fast typed UI development for chat and Security Lab | Separate backend app is required |
| Tailwind CSS | Fast consistent security-state UI | Utility classes can become verbose |
| IndexedDB + Dexie | Browser persistence for keys and ratchet state | Does not protect against XSS/malware |
| Node.js + Fastify | Lightweight typed API and WebSocket server | Less built-in structure than NestJS |
| PostgreSQL + Prisma | Strong relational model with type-safe access | ORM abstraction adds generated layer |
| Argon2id | Strong password hashing choice for new systems | Needs parameter tuning |
| JWT + refresh cookie | Stateless short-lived access with revocable refresh | Requires careful cookie/CSRF handling |
| libsodium + noble hashes | Reviewed primitives and explicit key schedule | Adds browser crypto dependency size |
| WebSocket | Transparent encrypted packet relay | Needs custom auth/reconnect handling |
| Vitest + Playwright | Unit and browser proof for protocol and UX | Requires disciplined test design |
| k6 + autocannon | Evidence for performance claims | Benchmarks must be documented carefully |

## 12. Reference Points

These references are used only to justify tool selection and design direction. The project still needs its own implementation, tests, and experiment results.

- React documentation: https://react.dev/
- Vite guide: https://vite.dev/guide/
- Tailwind CSS utility-first documentation: https://tailwindcss.com/docs/utility-first
- TypeScript documentation: https://www.typescriptlang.org/docs/
- Node.js documentation: https://nodejs.org/docs/latest/api/
- Fastify documentation: https://fastify.dev/docs/
- PostgreSQL documentation: https://www.postgresql.org/docs/
- Prisma documentation: https://www.prisma.io/docs/orm
- Dexie documentation: https://dexie.org/docs
- Libsodium documentation: https://libsodium.gitbook.io/doc/
- noble-hashes repository: https://github.com/paulmillr/noble-hashes
- jose repository and documentation entry point: https://github.com/panva/jose
- OWASP Password Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- Playwright documentation: https://playwright.dev/docs/intro
- Vitest documentation: https://vitest.dev/
- k6 documentation: https://k6.io/docs/
- autocannon repository: https://github.com/mcollina/autocannon
- Docker Compose documentation: https://docs.docker.com/compose/
