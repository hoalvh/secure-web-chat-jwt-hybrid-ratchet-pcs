# Key Schedule and Ratchet

This document describes the current demo key schedule and the intended ratchet behavior.

## Current Key Material

The current browser demo uses:

- ECDH P-256 device private key in IndexedDB.
- Contact ECDH P-256 public key from the server key directory.
- ECDH shared secret from Web Crypto.
- HKDF-SHA256 root key.
- Directional chain key.
- Per-message AES-GCM key.
- SHA-256 public key fingerprint for safety display.

The server stores only public key JWKs, fingerprints, ciphertext packets, and routing metadata.

## Current Derivation Flow

For each message, the browser derives:

```text
local private key + remote public key
-> ECDH P-256 shared secret
-> HKDF-SHA256 root key
-> directional chain key
-> per-message AES-GCM key
```

The current JavaScript labels are:

```text
root-from-ecdh
chain:v1:{conversation_id}:{sender}->{recipient}
next-chain-key:{step}
message-key:{message_number}
```

Different labels are used so the same bytes are not reused for multiple roles.

## Symmetric Ratchet

Conceptually:

```text
message_key_i   = HKDF(chain_key_i, "message-key:i")
chain_key_{i+1} = HKDF(chain_key_i, "next-chain-key:i")
```

The current demo recomputes the chain from the root key and message number instead of maintaining a production-grade rolling chain state for every skipped/out-of-order message. This keeps the UI demo simple but should be described as a simplified ratchet, not a complete deployment design.

## DH Ratchet and PCS

The DH ratchet goal is:

```text
old root key + fresh DH secret -> new root key and new chain keys
```

This is what gives post-compromise recovery: if an attacker temporarily learns current symmetric state but later loses access, a fresh DH step can introduce entropy the attacker does not know.

In the current runnable MVP, the full DH ratchet message flow is not implemented. The Security Lab endpoint `/lab/state-compromise` reports PCS-style metrics for a controlled scenario:

```text
compromise_at_message = 3
rekey_at_message = 5
total_messages = 8
```

The report should present this as a PCS demonstration metric, not as proof of a production Double Ratchet.

## AEAD Key Use

Each message is encrypted with AES-GCM:

- 256-bit key derived through HKDF.
- 96-bit random nonce.
- 128-bit authentication tag.
- Canonical packet header as associated data.

The AES-GCM associated data must include sender, recipient, device IDs, conversation ID, message number, and the ratchet/fingerprint marker. This prevents attackers from moving ciphertext between conversations or changing packet metadata silently.

## Key Erasure Rules

The implementation should avoid keeping unnecessary sensitive material:

- Do not log plaintext.
- Do not log message keys, root keys, chain keys, or private keys.
- Remove plaintext from temporary UI variables when practical.
- Treat IndexedDB private keys as sensitive demo state.
- Never send private key JWK field `d` to the backend.

JavaScript does not guarantee perfect memory erasure because of runtime garbage collection. The project should state this limitation and treat key erasure as an application-state rule.

## Test Vector Targets

The project should add deterministic tests or scripted checks for:

- Same ECDH/root inputs produce the same derived key.
- Different contacts produce different root keys.
- Different message numbers produce different message keys.
- Different directions produce different chain keys.
- Header changes cause AES-GCM decrypt failure.
- Replayed packet IDs are rejected by the lab/client logic.
- PCS lab metrics show a recovery point after DH rekey.

## Future Work

Future protocol work can add:

- Full DH ratchet state in the message flow.
- Skipped-message key handling.
- Out-of-order message support.
- Signed prekeys or X3DH-style session setup.
- Non-extractable browser private keys where demo inspection is no longer needed.
- A shared protocol package with test vectors.
