# Device Identity and Key Binding

This document describes how account identity is connected to cryptographic device identity in the current browser demo.

## Current Key Material

- Account ID: server-side username.
- Device ID: server-visible browser device identifier, usually `{username}-browser`.
- Device key: ECDH P-256 key pair generated in the browser through Web Crypto.
- Public key bundle: public JWK, device ID, username, fingerprint, and timestamps.
- Local private key: private JWK stored in IndexedDB.

The current implementation does not use Ed25519 identity signatures, signed prekeys, or one-time prekeys. Those remain future protocol work.

## Security UX Requirements

- Show a fingerprint for contacts.
- Warn when a known contact fingerprint changes.
- Make unverified and changed-key states visible in the chat UI.
- Keep the key-substitution scenario reproducible through backend lab endpoints and visible fingerprint state.

## Risk

If the server can replace Bob's public key without Alice noticing, end-to-end encryption can become encryption to the attacker. Key verification is therefore part of the security design, even in a small course demo.

## Current Technology Decisions

| Decision | Current choice | Reason |
|---|---|---|
| Device key agreement | ECDH P-256 via Web Crypto | Built into browsers and sufficient for the current E2EE demo |
| Public key format | JWK public key | Native Web Crypto import/export format |
| Public key directory | FastAPI + JSON demo store | Simple key lookup for local demo and lab evidence |
| Local private-key storage | IndexedDB native API | Browser-compatible persistence without a build dependency |
| Safety display | SHA-256 fingerprint of public JWK | Human-checkable indicator for key substitution warnings |

## Account and Device Identity

An account password proves that a user can log in to the server. It does not prove which cryptographic public key should be trusted for encrypted chat.

The project separates two identities:

| Identity | Controlled by | Purpose |
|---|---|---|
| Account identity | Server auth system | Login, session management, routing, device ownership |
| Device cryptographic identity | Client-generated private key | End-to-end encryption and trust state |

In the stolen-JWT experiment, the token may allow temporary server access, but it should not allow message decryption without the local browser private key.

## Device Registration

The browser calls `POST /devices` with:

- `device_id`
- `device_label`
- `public_key_jwk`
- `fingerprint`

The backend rejects a public key JWK if it includes the private-key field `d`. This is the most important server-side device-boundary check in the current MVP.

## Key Bundle Lookup

The sender fetches a contact key through:

```text
GET /keys/bundle/{username}
```

The response contains:

- Target user ID.
- Device ID.
- Public key JWK.
- Fingerprint.
- Creation timestamp.

The server is trusted for availability and routing, but not for silent key honesty. The UI must still expose fingerprints and key changes.

## IndexedDB for Local Keys

The current browser stores:

- Device private JWK.
- Device public JWK.
- Fingerprint.
- Per-contact saved fingerprint/safety state.

This keeps private keys out of the backend. It does not protect against XSS, malicious extensions, or a fully compromised browser.

For manual decrypt evidence, a developer may export the IndexedDB device record to an ignored file such as `tmp/alice-device.json` and run:

```powershell
node scripts\decrypt_message.mjs --device .\tmp\alice-device.json --index 0
```

That export contains `privateKeyJwk` and must never be committed.

## Key-Change Handling

When a saved contact fingerprint differs from the fetched fingerprint, the UI must show `Key changed`.

Current backend/demo behavior:

- `/lab/key-substitution` records a key-substitution event.
- The user UI compares fingerprints when opening a contact and shows a warning if the saved value changes.
- The admin dashboard can show public-key records and security events for evidence.

Future UX can pause sending until the user explicitly accepts or verifies the new fingerprint.

## Future Work

Future protocol work can add:

- Ed25519 identity signatures.
- Signed prekeys.
- One-time prekeys.
- Full X3DH-style initial session setup.
- QR or numeric safety-number comparison.
- Key transparency or an append-only audit log.
- Multi-device identity binding.
