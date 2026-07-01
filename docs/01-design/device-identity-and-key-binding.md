# Device Identity and Key Binding

This document describes how account identity is connected to cryptographic device identity in the current browser demo.

## Current Key Material

- Account ID: server-side username.
- Device ID: server-visible browser device identifier, usually `{username}-browser`.
- Device key: ECDH P-256 key pair generated in the browser through Web Crypto.
- Identity signing key: ECDSA P-256 key generated in the browser and wrapped locally with a password-derived AES-GCM key.
- Public key bundle: device public JWK, identity signing public JWK, signed pre-key, optional one-time pre-key, device ID, username, fingerprint, and timestamps.
- Local private key material: device private JWK, identity signing key wrapper, signed pre-key private JWK, one-time pre-key private JWKs, and dynamic session state stored in IndexedDB.

The current implementation uses ECDSA/P-256 identity signatures and an X3DH-style teaching flow. It is not Signal-compatible X3DH and does not implement a full Double Ratchet.

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
| Public key directory | FastAPI + SQLAlchemy database (`devices` table) | Simple key lookup for local demo and lab evidence |
| Local private-key storage | IndexedDB native API | Browser-compatible persistence without a build dependency |
| Safety display | SHA-256 fingerprint of identity/device public JWK | Human-checkable indicator for key substitution warnings |

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
- `device_signature` when an identity signing key is available

The backend rejects nested private key material in device, signing-key, pre-key, and message submissions. This is the most important server-side key-boundary check in the current MVP.

## Key Bundle Lookup

The sender fetches a contact key through:

```text
GET /keys/bundle/{username}
GET /keys/bundle/{username}?reserve_otp=true   # only when starting a new session
```

The response contains:

- Target user ID.
- Device ID.
- Public key JWK.
- Fingerprint.
- Identity signing public key.
- Device signature.
- Signed pre-key.
- One available one-time pre-key only when `reserve_otp=true`; the server marks that OTP consumed in the same transaction.
- Creation timestamp.

The server is trusted for availability and routing, but not for silent key honesty. The UI must still expose fingerprints, verify signatures, and block sending when a known identity changes or a signature is invalid.

## IndexedDB for Local Keys

The current browser stores:

- Device private JWK.
- Device public JWK.
- Fingerprint.
- Wrapped identity signing key.
- Signed pre-key and one-time pre-key private JWKs.
- Dynamic session root/chain state and local encrypted packet history.
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

The current UI blocks sending on identity change or invalid signatures. Future UX can add an explicit verified safety-number ceremony for legitimate device replacement.

## Future Work

Future protocol work can add:

- Ed25519/X25519 or another audited protocol suite.
- Signal-compatible X3DH and Double Ratchet.
- QR or numeric safety-number comparison.
- Key transparency or an append-only audit log.
- Multi-device identity binding.
