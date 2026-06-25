# Protocol Design

This document describes the current end-to-end encryption design. The protocol is Signal-inspired but simplified for a course prototype. It must not be presented as production-ready or as a full Signal implementation.

## Scope

The implementation should demonstrate:

- Separation between JWT authentication and message encryption.
- Client-side device keys.
- Public key lookup through the server.
- Per-message key derivation.
- AEAD encryption with associated data.
- Replay and tamper experiments.
- Key-substitution warning.
- Forward secrecy and post-compromise security concepts.

Product features such as group chat, file sharing, push notifications, search, account recovery, and full multi-device sync are out of scope unless they directly support the security demo.

## Current Components

Current browser-side primitives:

- ECDH P-256 through Web Crypto.
- HKDF-SHA256 through Web Crypto.
- AES-GCM through Web Crypto.
- SHA-256 fingerprints through Web Crypto.
- Random 96-bit AES-GCM nonces through Web Crypto.

Current server-side role:

- Authenticate users.
- Store public device keys.
- Store and relay encrypted packets.
- Reject plaintext packet submissions.
- Reject device registrations that include private JWK material.
- Provide admin/dashboard evidence and Security Lab endpoints.

The server does not decrypt message ciphertext.

## Current Session Model

The current MVP uses a simple public key directory:

1. A browser generates an ECDH P-256 device key pair.
2. The private key stays in IndexedDB.
3. The browser publishes the public key JWK and SHA-256 fingerprint to `/devices`.
4. A sender fetches the recipient bundle from `/keys/bundle/{username}`.
5. The sender derives an ECDH shared secret with the recipient public key.
6. HKDF derives a root key and per-message keys.
7. AES-GCM encrypts the plaintext locally.
8. The server stores and relays only the encrypted packet.

This is enough for the course demo but does not implement full X3DH, signed prekeys, skipped-message keys, or full Double Ratchet behavior.

## Manual Decryption Requirements

To decrypt one stored ciphertext outside the browser, the same inputs and algorithm are required:

- Server store (SQLite/PostgreSQL database) containing the selected packet and peer public device key.
- Local browser device private key JWK for either the sender or recipient.
- Packet header exactly as stored.
- Packet `nonce`, `ciphertext`, and `tag`.
- Same derivation labels used by the frontend:
  - `root-from-ecdh`
  - `chain:v1:{conversation_id}:{sender}->{recipient}`
  - `next-chain-key:{step}`
  - `message-key:{message_number}`

Current helper:

```powershell
node scripts\decrypt_message.mjs --list
node scripts\decrypt_message.mjs --device .\tmp\<exported-device>.json --index 0
```

If any input differs, AES-GCM authentication fails instead of returning plaintext.

## Message Packet

Each encrypted message packet contains:

- `version`
- `algorithm`
- `header`
- `nonce`
- `ciphertext`
- `tag`

Current algorithm label:

```text
ECDH-P-256+HKDF-SHA256+AES-GCM
```

Current header fields:

| Field | Purpose |
|---|---|
| `version` | Protocol version |
| `conversation_id` | Stable conversation identifier |
| `sender_user_id` | Authenticated sender user |
| `sender_device_id` | Sender browser device |
| `recipient_user_id` | Recipient user |
| `recipient_device_id` | Recipient browser device |
| `message_number` | Per-direction message counter |
| `ratchet_public_key` | Current demo fingerprint/ratchet marker |

The canonical JSON header is passed as AES-GCM associated data. If an attacker changes routing metadata or ciphertext, decryption should fail.

## Replay and Tamper Handling

Tamper handling relies on AES-GCM authentication:

```text
modified header or ciphertext -> AES-GCM tag verification fails
```

Replay handling in the current browser/lab flow tracks packet IDs derived from:

```text
conversation_id:sender_user_id:recipient_user_id:message_number
```

The backend lab endpoints use this to demonstrate duplicate packet detection. A production design would need a more complete replay window and skipped-message handling.

## Key Substitution Handling

The server is a public key directory. If it maliciously replaces Bob's public key, Alice can still perform ECDH, but she would be encrypting to the wrong key.

The UI therefore shows fingerprints and key-change warnings. This does not fully solve first-contact trust, but it makes the risk visible for the demo and report.

## Signal-Inspired Limits

The project borrows the ideas of per-message keys, ratcheting, forward secrecy, and post-compromise recovery. The current implementation is intentionally simplified:

- It uses one browser ECDH P-256 device key per user in the demo.
- It derives deterministic per-message keys from a root key and message number.
- It does not implement full X3DH.
- It does not implement signed prekeys.
- It does not implement full Double Ratchet message flow.
- The PCS/DH rekey behavior is currently shown through Security Lab metrics rather than complete message-flow rekeying.

These limits should be stated clearly in the final report.

## Alternative Designs Considered

| Alternative | Why not used in current MVP |
|---|---|
| Plain TLS chat | TLS protects transport only; the server could still read messages |
| Static shared room key | Simple, but weak for forward secrecy and no PCS story |
| Symmetric ratchet only | Shows per-message keys, but cannot recover after current chain-state compromise |
| Full Signal protocol | Stronger, but too large for the course deadline |
| X25519/Ed25519/libsodium stack | Good future path, but the current browser demo uses built-in Web Crypto P-256 |
| MLS group messaging | Interesting, but group messaging expands the project beyond MVP |

## Implementation Rules

- Do not implement low-level cryptographic primitives manually.
- Keep plaintext only inside sender and recipient clients.
- Include important packet headers in AEAD associated data.
- Reject unsupported protocol versions.
- Reject packets containing plaintext before storage.
- Reject private key material submitted to the backend.
- Keep protocol tests independent from UI styling.
