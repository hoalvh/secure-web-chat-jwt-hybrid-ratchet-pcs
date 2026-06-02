# Key Schedule

This document specifies the key schedule and key erasure rules.

## Key Types

- Root key.
- Sending chain key.
- Receiving chain key.
- Message key.
- Identity key pair.
- Signed prekey pair.
- Ratchet key pair.

## Symmetric Ratchet

```text
message_key_i   = HKDF(chain_key_i, "message-key")
chain_key_{i+1} = HKDF(chain_key_i, "next-chain-key")
```

After encrypting or decrypting a message, the message key and old chain key should be erased from memory where practical.

## DH Ratchet

```text
dh_secret = X25519(local_new_ratchet_private, remote_ratchet_public)
root_key' = HKDF(root_key, dh_secret, "dh-ratchet")
```

The DH ratchet is the main mechanism for post-compromise recovery.

## Library Decisions

| Function | Choice | Reason |
|---|---|---|
| Key agreement | X25519 from libsodium | Avoids manual elliptic-curve implementation and fits the DH ratchet model |
| Message encryption | XChaCha20-Poly1305 from libsodium | AEAD gives confidentiality plus tamper detection; large nonce space reduces accidental nonce-collision risk |
| Key derivation | HKDF-SHA-256 through a reviewed library | HKDF is suitable for deriving independent keys from root/chain material |
| Hashing/fingerprints | SHA-256 through `@noble/hashes` or equivalent | Useful for fingerprints, safety numbers, and deterministic test vectors |
| Randomness | Cryptographic random bytes from libsodium/Web Crypto boundary | Ratchet keys, nonces, and prekeys must not use normal pseudorandom functions |

## Key Schedule Purpose

The project should not reuse one encryption key for all messages. The key schedule derives:

- Root keys for long-running session evolution.
- Sending chain keys for messages sent by the local device.
- Receiving chain keys for messages received from the remote device.
- One-time message keys for AEAD encryption/decryption.

This structure also makes state-leak experiments easier to define.

## HKDF Labels

Different labels must be used for different derived values so keys are separated by purpose.

Initial labels:

| Label | Output |
|---|---|
| `root-from-x3dh` | Initial root key |
| `dh-ratchet-root` | New root key after DH ratchet |
| `dh-ratchet-chain` | New sending/receiving chain key |
| `message-key` | AEAD message key |
| `next-chain-key` | Next chain key |
| `header-fingerprint` | Optional display/test helper |

Using labels prevents accidental reuse of the same derived bytes for multiple roles.

## Symmetric Ratchet Limitation

The symmetric ratchet updates keys in one direction:

```text
chain_key_i -> message_key_i
chain_key_i -> chain_key_{i+1}
```

This protects old messages if old keys are erased. However, if an attacker steals `chain_key_i`, the attacker can compute future chain keys until fresh external entropy enters the session.

The DH ratchet is added to bring fresh Diffie-Hellman material into the session.

## DH Ratchet Role

The DH ratchet mixes a new Diffie-Hellman output into the root key:

```text
root_key, dh_secret -> new_root_key, new_chain_key
```

If the attacker temporarily compromises local state but later loses access, a future DH exchange can create keys the attacker cannot derive. This is the post-compromise security behavior the project should test.

## Key Erasure Rules

The implementation should erase or overwrite sensitive values where practical:

- Erase each `message_key` after encryption/decryption.
- Erase old `chain_key` after deriving the next chain key.
- Replace old root keys after DH ratchet.
- Avoid logging plaintext, message keys, chain keys, root keys, private keys, or raw ratchet state.

JavaScript does not guarantee perfect memory erasure because of runtime garbage collection. The project should state this limitation and treat key erasure as an application-state rule, not a low-level memory guarantee.

## Test Vectors

The project should add deterministic tests for:

- Same input key material produces the same derived keys.
- Different labels produce different outputs.
- Different message counters produce different message keys.
- Old message keys are removed from application state after use.
- A leaked chain key cannot decrypt messages before that chain key if old keys were erased.
- A leaked chain key can decrypt future messages until DH rekey, demonstrating why DH ratchet is necessary.
