# Results

This document will summarize benchmark and security experiment results.

## Result Summary Table

| Variant | Attack scenario | Messages exposed | Replay accepted | Tamper accepted | PCS recovery window | Notes |
|---|---|---:|---:|---:|---:|---|
| Plain relay | Server compromise | TBD | N/A | N/A | N/A | Baseline |
| Symmetric ratchet | State compromise | TBD | TBD | TBD | TBD | No DH recovery |
| DH ratchet | State compromise | TBD | TBD | TBD | TBD | Expected recovery after rekey |

## Raw Data

Raw benchmark outputs should be stored under `benchmarks/results/`.

## Result Structure

The project should report both security outcomes and performance cost.

Results are split into:

- Security results: what the attacker can or cannot access.
- Performance results: latency, throughput, and overhead.
- UX evidence: screenshots or browser-test outputs showing warnings and recovery states.

## Required Security Result Tables

### Server Compromise

| Run | Stored plaintext visible | Private keys visible | Ciphertext rows visible | Notes |
|---|---:|---:|---:|---|
| Baseline plain relay | TBD | TBD | TBD | Expected insecure baseline |
| Final E2EE design | TBD | TBD | TBD | Expected ciphertext-only |

### Stolen JWT

| Run | API access allowed | Ciphertext fetched | Plaintext decrypted | Reason |
|---|---:|---:|---:|---|
| Stolen access JWT | TBD | TBD | TBD | JWT should not include local private keys |

### Replay and Tamper

| Run | Replay accepted | Tamper accepted | Failure reason | Notes |
|---|---:|---:|---|---|
| Replay old packet | TBD | N/A | Duplicate counter or replay window | TBD |
| Modify ciphertext | N/A | TBD | AEAD failure | TBD |
| Modify associated data | N/A | TBD | AEAD failure | TBD |

### Post-Compromise Security

| Variant | Compromise at message | Rekey at message | Future messages exposed before rekey | Future messages exposed after rekey | Notes |
|---|---:|---:|---:|---:|---|
| Symmetric ratchet only | TBD | N/A | TBD | N/A | Expected no recovery without new entropy |
| Hybrid DH ratchet | TBD | TBD | TBD | TBD | Expected recovery after DH ratchet |

## Required Performance Result Tables

### Authentication and API

| Benchmark | p50 latency | p95 latency | throughput | Notes |
|---|---:|---:|---:|---|
| Login with Argon2id | TBD | TBD | TBD | Parameters should be recorded |
| JWT verification | TBD | TBD | TBD | Should be low overhead |
| Refresh token | TBD | TBD | TBD | Includes database lookup |

### Messaging and Crypto

| Benchmark | p50 latency | p95 latency | bytes overhead | Notes |
|---|---:|---:|---:|---|
| Encrypt one message | TBD | TBD | TBD | Client-side |
| Decrypt one message | TBD | TBD | TBD | Client-side |
| DH ratchet rekey | TBD | TBD | TBD | PCS recovery cost |
| Relay ciphertext packet | TBD | TBD | TBD | Server does not decrypt |

## Interpretation Rules

- Security results should be explained before performance results.
- If a result fails, keep it and explain the cause instead of deleting it.
- Compare final design against at least one weaker baseline.
- Record environment details: machine, browser, Node version, database mode, and test data size.
- Do not claim production-grade security from a course prototype.
