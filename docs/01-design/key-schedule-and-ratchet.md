# Key Schedule and Ratchet

This document describes the current demo key schedule and the intended ratchet behavior.

## Current Key Material

The current browser demo uses:

- ECDH P-256 device private key in IndexedDB.
- ECDSA P-256 identity signing key wrapped locally with a password-derived AES-GCM key.
- Signed pre-key and one-time pre-key private material in IndexedDB.
- Contact ECDH P-256 public key from the server key directory.
- ECDH shared secret from Web Crypto.
- X3DH-style session root key for version 3 packets.
- Directional session chain key.
- Per-message AES-GCM key.
- SHA-256 public key fingerprint for safety display.

The server stores only public key JWKs, fingerprints, stored/offline ciphertext packets, and routing metadata. Live online packets can be relayed without being written to the server database.

## Current Derivation Flow

For version 3 session messages, the browser derives:

```text
device/pre-key DH inputs
-> X3DH-style root key
-> session-chain:v3:{session_id}:{sender}->{recipient}
-> per-message AES-GCM key
```

The version 3 session setup uses this X3DH-style DH order:

```text
DH1 = sender device identity private x recipient signed pre-key public
DH2 = sender ephemeral private x recipient device identity public
DH3 = sender ephemeral private x recipient signed pre-key public
DH4 = sender ephemeral private x recipient one-time pre-key public, if reserved
```

The recipient mirrors those inputs with its signed pre-key private key, device
identity private key, and one-time pre-key private key. The recipient stores the
new inbound session only after AES-GCM authentication succeeds, then deletes the
local one-time pre-key private material if DH4 was used.

Legacy version 1 packets still use the older static-device fallback:

```text
root-from-ecdh
chain:v1:{conversation_id}:{sender}->{recipient}
next-chain-key:{step}
message-key:{message_number}
```

Current version 3 labels are:

```text
x3dh-root
session-chain:v3:{session_id}:{sender}->{recipient}
session-next-chain-key:{step}
session-message-key:{message_number}
```

Different labels are used so the same bytes are not reused for multiple roles.

The same labels are used by `scripts/decrypt_message.mjs`, so manual decryption checks the real app algorithm rather than a separate ad-hoc flow.

## Symmetric Ratchet

Conceptually:

```text
message_key_i   = HKDF(chain_key_i, "message-key:i")
chain_key_{i+1} = HKDF(chain_key_i, "next-chain-key:i")
```

The current demo keeps a local session root and send/receive counters, then recomputes the needed chain position from the root key and message number. This keeps the UI demo simple but should be described as a simplified dynamic session chain, not a complete Double Ratchet with skipped-message keys.

## DH Ratchet and PCS

The DH ratchet goal is:

```text
old root key + fresh DH secret -> new root key and new chain keys
```

This is what gives post-compromise recovery: if an attacker temporarily learns current symmetric state but later loses access, a fresh DH step can introduce entropy the attacker does not know.

In the current runnable MVP, the full DH ratchet message flow is not implemented. The backend endpoint `/lab/state-compromise` reports PCS-style metrics for a controlled scenario:

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
- `scripts/decrypt_message.mjs` decrypts a real stored packet when given the correct exported browser private key.

## Future Work

Future protocol work can add:

- Full DH ratchet state in the message flow.
- Skipped-message key handling.
- Out-of-order message support.
- Signal-compatible X3DH test vectors and a formal transcript format.
- Non-extractable browser private keys where demo inspection is no longer needed.
- A shared protocol package with test vectors.
