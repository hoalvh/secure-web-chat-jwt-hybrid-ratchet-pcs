# Results

This document summarizes benchmark and security experiment results for the current runnable MVP. Values marked `not yet measured` are intentionally left open until a real benchmark or screenshot/evidence run is recorded.

## Result Summary Table

| Variant | Attack scenario | Messages exposed | Replay accepted | Tamper accepted | PCS recovery window | Notes |
|---|---|---:|---:|---:|---:|---|
| Plain relay | Server compromise | All plaintext if stored | N/A | N/A | N/A | Insecure baseline for explanation only |
| Current Web Crypto demo | Server compromise | 0 plaintext rows expected | Lab endpoint only | AES-GCM expected reject | PCS metric only | FastAPI + SQLite/PostgreSQL + browser E2EE |
| Future full DH ratchet | State compromise | not yet implemented | not yet implemented | not yet implemented | not yet implemented | Expected recovery after real DH ratchet |

## Raw Data

Raw outputs should be stored under:

```text
docs/02-evaluation/
```

If the team later adds real benchmark scripts or raw screenshot sets, create a dedicated evidence folder at that time. Do not keep empty placeholder folders in the repository.

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
| Baseline plain relay | yes, by design | N/A | N/A | Explanation baseline, not the current app |
| Current E2EE demo | no | no | yes | Database/admin dashboard show hashes, public keys, nonce, ciphertext, tag |

### Stolen JWT

| Run | API access allowed | Ciphertext fetched | Plaintext decrypted | Reason |
|---|---:|---:|---:|---|
| Stolen access JWT | yes, until expiry | yes, if API request is authorized | no without browser private key | JWT should not include browser private keys |

### Replay and Tamper

| Run | Replay accepted | Tamper accepted | Failure reason | Notes |
|---|---:|---:|---|---|
| Replay old packet | lab/demo check expected reject | N/A | Duplicate packet ID/message counter | Needs recorded endpoint output |
| Modify ciphertext | N/A | expected reject | AES-GCM tag failure | Needs recorded endpoint output |
| Modify associated data | N/A | expected reject | AES-GCM tag failure | Needs recorded endpoint output |

### Post-Compromise Security

| Variant | Compromise at message | Rekey at message | Future messages exposed before rekey | Future messages exposed after rekey | Notes |
|---|---:|---:|---:|---:|---|
| Symmetric ratchet only | not yet measured | N/A | not yet measured | N/A | Expected no recovery without new entropy |
| Current PCS lab metric | 3 | 5 | 2 before rekey in demo metric | 0 after rekey in demo metric | Demonstration metric, not full Double Ratchet proof |
| Future full DH ratchet | not implemented | not implemented | not implemented | not implemented | Expected recovery after DH ratchet |

## Required Performance Result Tables

### Authentication and API

| Benchmark | p50 latency | p95 latency | throughput | Notes |
|---|---:|---:|---:|---|
| Login with Argon2id | not yet measured | not yet measured | not yet measured | Parameters should be recorded |
| JWT verification | not yet measured | not yet measured | not yet measured | HMAC-SHA256 in current FastAPI app |
| Refresh token | not yet measured | not yet measured | not yet measured | Includes database lookup |

### Messaging and Crypto

| Benchmark | p50 latency | p95 latency | bytes overhead | Notes |
|---|---:|---:|---:|---|
| Encrypt one message | not yet measured | not yet measured | not yet measured | Browser Web Crypto |
| Decrypt one message | not yet measured | not yet measured | not yet measured | Browser Web Crypto and Node helper can verify one stored packet |
| PCS rekey metric | not latency-based | not latency-based | N/A | Lab metric |
| Relay ciphertext packet | not yet measured | not yet measured | not yet measured | Server does not decrypt |

## Interpretation Rules

- Security results should be explained before performance results.
- If a result fails, keep it and explain the cause instead of deleting it.
- Compare final design against at least one weaker baseline where possible.
- Record environment details: machine, OS, Python version, browser, server mode, and demo data size.
- Do not claim production-grade security from a course prototype.
