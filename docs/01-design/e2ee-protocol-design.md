# Protocol Design

This document describes the planned end-to-end encryption protocol.

## Scope

The protocol is Signal-inspired but simplified for this project. It is not a full Signal implementation and should not be presented as production-ready.

The implementation should cover:

- Correct separation between authentication and encryption.
- Clear key schedule.
- Per-message encryption keys.
- AEAD associated data.
- Replay rejection.
- Forward secrecy experiment.
- Post-compromise security experiment.
- Limitations.

Chat-product features such as avatars, message search, read receipts, file sharing, profile pages, and notifications are out of scope unless they support the security demo.

## Components

- Initial session setup using an X3DH-inspired prekey flow.
- Root key derived using HKDF.
- Sending and receiving chain keys.
- Per-message message keys.
- AEAD encryption with associated data.
- Symmetric ratchet for per-message key evolution.
- DH ratchet for post-compromise recovery.
- Replay protection using message counters.
- Optional skipped-message key handling for out-of-order messages.

## Message Packet

Each encrypted message should include:

- Protocol version.
- Conversation ID.
- Sender user ID.
- Sender device ID.
- Recipient user ID.
- Recipient device ID.
- Ratchet public key.
- Message number.
- Nonce.
- Ciphertext.

Header fields must be included in associated data.

## Technology and Library Decisions

| Decision | Choice | Reason |
|---|---|---|
| Crypto primitive library | `libsodium-wrappers-sumo` | Provides reviewed high-level primitives instead of hand-written cryptography |
| Hash/KDF helpers | `@noble/hashes` | Keeps HKDF/SHA-256 behavior explicit, typed, and testable |
| Key agreement | X25519 | Fits Signal-inspired DH ratchet design and modern elliptic-curve key exchange |
| Identity signatures | Ed25519 | Used to sign device prekeys and bind prekeys to long-term device identity |
| Message encryption | XChaCha20-Poly1305 | AEAD provides confidentiality and integrity; large nonce space is convenient for message encryption |
| Packet transport | WebSocket | Allows direct encrypted packet relay and easy lab inspection |
| Shared package | `packages/protocol` | Prevents client/server packet-format drift |

## Signal-Inspired Protocol

The project needs to demonstrate forward secrecy and post-compromise security, not just encrypted storage. A static shared key or simple AES encryption would only show confidentiality at one point in time.

A Signal-inspired ratchet is chosen because it gives the project three visible security properties:

- **Per-message key evolution:** each message uses a different message key.
- **Forward secrecy:** after key erasure, current state should not decrypt old messages.
- **Post-compromise recovery:** a later DH ratchet can introduce fresh entropy after temporary state exposure.

The design should be described as "Signal-inspired", not as a full Signal implementation.

## WebSocket Instead of Socket.IO

WebSocket is selected because the project benefits from a transparent relay layer. The server forwards encrypted packets and does not need higher-level room/event abstractions.

Socket.IO is useful in many chat apps, but it adds protocol behavior that is not needed for this MVP. A direct WebSocket frame keeps the data path easier to inspect:

```text
browser encrypts plaintext
-> sends encrypted packet over WebSocket
-> server relays ciphertext
-> recipient decrypts locally
```

## AEAD Requirement

The protocol must use authenticated encryption, not encryption alone. AEAD binds ciphertext to associated data so tampering with sender, recipient, device ID, counters, or ratchet headers is detected.

Associated data should include:

- Protocol version.
- Conversation ID.
- Sender user ID and device ID.
- Recipient user ID and device ID.
- Ratchet public key.
- Message number.
- Previous-chain length if implemented.

## Shared Packet Ownership

Packet definitions belong in `packages/protocol/` because both the client and server need to understand the same outer packet shape.

The client uses packet definitions to encrypt, decrypt, and validate local state. The server uses packet definitions only to validate routing metadata and store/relay ciphertext. The server must not contain plaintext parsing logic.

## Alternative Designs Considered

| Alternative | Why not chosen |
|---|---|
| Plain TLS chat | TLS protects transport only; the server can still read messages |
| Static shared room key | Simple, but weak for forward secrecy and no post-compromise recovery |
| Symmetric ratchet only | Good for per-message keys, but cannot recover after current ratchet state is compromised |
| Full Signal protocol | Stronger, but too large for the course scope |
| MLS group messaging | Interesting, but group messaging would expand the project beyond the MVP |

## Implementation Rules

- Do not manually implement X25519, Ed25519, AEAD, HKDF, or random generation.
- Keep plaintext only inside the sender and recipient clients.
- Include all relevant header fields in associated data.
- Reject packets with unsupported protocol versions.
- Reject duplicate or replayed message counters.
- Keep protocol tests independent from React and Fastify.
