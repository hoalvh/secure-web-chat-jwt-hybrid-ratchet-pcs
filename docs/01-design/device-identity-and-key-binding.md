# Device Identity and Key Binding

This document describes how account identity is connected to cryptographic device identity.

## Key Material

- Account ID: server-side user identity.
- Device ID: server-visible device identifier.
- Identity key: Ed25519 key pair generated on the client.
- Signed prekey: X25519 public key signed by the identity key.
- One-time prekeys: optional X25519 prekeys for asynchronous session setup.

## Security UX Requirements

- Show a safety number or fingerprint for contacts.
- Warn when a contact identity key changes.
- Allow users to verify, continue unverified, or block a conversation.

## Risk

If the server can replace Bob's public key without Alice noticing, end-to-end encryption can be downgraded into encryption to the attacker. Key verification is therefore part of the security design.

## Technology Decisions

| Decision | Choice | Reason |
|---|---|---|
| Long-term device identity | Ed25519 key pair | A signing key gives each device a stable cryptographic identity |
| Signed prekey | X25519 key signed by Ed25519 identity key | Enables asynchronous session setup while binding the prekey to the device identity |
| Public key directory | Fastify + PostgreSQL + Prisma | Server can store and serve public key bundles with ownership constraints |
| Local private-key storage | IndexedDB through Dexie | Browser-compatible structured persistence for private keys and ratchet state |
| Safety number | Hash/fingerprint of identity public keys | Gives users a human-checkable way to detect key substitution |

## Account and Device Identity

An account password proves that a user can log in to the server. It does not prove which cryptographic device key should be trusted for encrypted chat.

The project separates two identities:

| Identity | Controlled by | Purpose |
|---|---|---|
| Account identity | Server auth system | Login, session management, routing, device ownership |
| Device cryptographic identity | Client-generated private key | End-to-end encryption trust and prekey signing |

In the stolen-JWT experiment, the token may allow temporary server access, but it should not allow message decryption without local private keys.

## Ed25519 Identity Key

Ed25519 is used for identity signatures because the device needs to sign public prekeys. A recipient can verify that a signed prekey belongs to the claimed long-term identity key.

The server can publish public keys, but the client still checks whether a signed prekey is bound to the expected identity key. This does not solve first-contact trust by itself, so the UI still needs safety numbers or key-change warnings.

## X25519 Prekeys and Ratchet Keys

X25519 is used for key agreement because the project needs Diffie-Hellman outputs for initial session setup and DH ratchet recovery.

The roles are separated:

- Ed25519 signs.
- X25519 performs key agreement.
- HKDF derives root, chain, and message keys.
- AEAD encrypts message payloads.

## IndexedDB/Dexie for Local Keys

Device keys and ratchet state must survive page reloads. IndexedDB is the browser storage layer intended for structured client-side data. Dexie makes that storage easier to use safely from TypeScript.

The project should store:

- Private identity key.
- Signed prekey private key.
- Ratchet private key.
- Current root key.
- Sending and receiving chain state.
- Verification status for contacts.

The server must store only public key material and ciphertext.

## Key-Change Handling

When a contact identity key changes, the client must not silently continue as if nothing happened.

Required UI decisions:

- Show a strong warning.
- Mark the conversation as `Key changed`.
- Pause sending or require explicit user confirmation.
- Allow the user to compare the new safety number.
- Record the event for the Security Lab demonstration.

## Alternative Designs Considered

| Alternative | Why not chosen |
|---|---|
| Account password derives E2EE key | Password changes and server login flow would become entangled with message security |
| Server-generated device keys | Server would know private keys, breaking end-to-end encryption |
| No key verification UI | Key substitution attack becomes invisible to the user |
| Multi-device full sync | Valuable, but too large for MVP scope |
