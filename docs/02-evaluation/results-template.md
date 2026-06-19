# Results

This document summarizes benchmark and security experiment results. Replace `TBD` with actual measured values when experiments are run.

## Result Summary Table

| Variant | Attack scenario | Messages exposed | Replay accepted | Tamper accepted | PCS recovery window | Notes |
|---|---|---:|---:|---:|---:|---|
| Plain relay | Server compromise | TBD | N/A | N/A | N/A | Insecure baseline |
| Current Web Crypto demo | Server compromise | TBD | TBD | TBD | TBD | FastAPI + JSON store + browser E2EE |
| Future full DH ratchet | State compromise | TBD | TBD | TBD | TBD | Expected recovery after rekey |

## Raw Data

Raw outputs should be stored under:

```text
benchmarks/results/
experiments/<scenario>/
```

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
| Current E2EE demo | TBD | TBD | TBD | Expected ciphertext-only JSON store |

### Stolen JWT

| Run | API access allowed | Ciphertext fetched | Plaintext decrypted | Reason |
|---|---:|---:|---:|---|
| Stolen access JWT | TBD | TBD | TBD | JWT should not include browser private keys |

### Replay and Tamper

| Run | Replay accepted | Tamper accepted | Failure reason | Notes |
|---|---:|---:|---|---|
| Replay old packet | TBD | N/A | Duplicate packet ID/message counter | TBD |
| Modify ciphertext | N/A | TBD | AES-GCM tag failure | TBD |
| Modify associated data | N/A | TBD | AES-GCM tag failure | TBD |

### Post-Compromise Security

| Variant | Compromise at message | Rekey at message | Future messages exposed before rekey | Future messages exposed after rekey | Notes |
|---|---:|---:|---:|---:|---|
| Symmetric ratchet only | TBD | N/A | TBD | N/A | Expected no recovery without new entropy |
| Current PCS lab metric | TBD | TBD | TBD | TBD | Demonstration metric, not full Double Ratchet proof |
| Future full DH ratchet | TBD | TBD | TBD | TBD | Expected recovery after DH ratchet |

## Required Performance Result Tables

### Authentication and API

| Benchmark | p50 latency | p95 latency | throughput | Notes |
|---|---:|---:|---:|---|
| Login with Argon2id | TBD | TBD | TBD | Parameters should be recorded |
| JWT verification | TBD | TBD | TBD | HMAC-SHA256 in current FastAPI app |
| Refresh token | TBD | TBD | TBD | Includes JSON store lookup |

### Messaging and Crypto

| Benchmark | p50 latency | p95 latency | bytes overhead | Notes |
|---|---:|---:|---:|---|
| Encrypt one message | TBD | TBD | TBD | Browser Web Crypto |
| Decrypt one message | TBD | TBD | TBD | Browser Web Crypto |
| PCS rekey metric | TBD | TBD | TBD | Lab metric |
| Relay ciphertext packet | TBD | TBD | TBD | Server does not decrypt |

## Interpretation Rules

- Security results should be explained before performance results.
- If a result fails, keep it and explain the cause instead of deleting it.
- Compare final design against at least one weaker baseline where possible.
- Record environment details: machine, OS, Python version, browser, server mode, and demo data size.
- Do not claim production-grade security from a course prototype.
