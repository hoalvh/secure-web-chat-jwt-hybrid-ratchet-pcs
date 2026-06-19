# Experiments

This document tracks the planned security experiments for the current FastAPI/Web Crypto prototype.

## Scope

Experiments check whether the encrypted chat design behaves as expected under controlled attacker scenarios.

Priority work:

- Show that the server stores ciphertext only.
- Distinguish stolen JWT from E2EE key compromise.
- Demonstrate replay and tamper rejection.
- Demonstrate key-substitution warning.
- Measure or explain forward secrecy and post-compromise recovery limits.
- Record actual results, not only expected results.

## Required Experiments

1. Server compromise.
2. Stolen JWT.
3. Replay and tamper.
4. Key substitution.
5. Forward secrecy.
6. Post-compromise security.

## Experiment Template

Each experiment should include:

- Objective.
- Setup.
- Attack steps.
- Expected result.
- Actual result.
- Metrics.
- Notes and limitations.

## Current Tooling Decisions

| Need | Current choice | Reason |
|---|---|---|
| Backend security-boundary tests | Pytest + FastAPI TestClient | Already verifies auth/device/message/lab rules |
| Manual browser evidence | Local browser at `http://127.0.0.1:8000` | Current UI has no build step and is easy to demo |
| Raw evidence storage | `docs/02-evaluation/` until real scripts exist | Keeps result notes close to the evaluation docs |
| Future browser tests | Playwright | Good next step for warning and lab-state verification |
| Future API benchmarks | k6 or a Python/httpx script | Current backend is FastAPI, not Fastify |

## Security Claims to Check

| Claim | Experiment |
|---|---|
| Server cannot read plaintext | Server compromise database/store inspection |
| JWT does not decrypt messages | Stolen JWT fetch-and-decrypt attempt |
| AES-GCM detects modification | Tamper attack |
| Packet IDs detect duplicates | Replay attack |
| Safety UX detects key substitution | Malicious key directory simulation |
| Symmetric key evolution protects past messages | State leak after old keys are erased |
| DH rekey supports PCS concept | State leak followed by rekey metric and future-message analysis |

## Baselines

The experiments should compare against weaker variants where possible:

| Variant | Purpose |
|---|---|
| Plain relay baseline | Shows what happens if the server stores readable plaintext |
| Static-key or symmetric-only variant | Shows limitations before DH recovery is added |
| Current Web Crypto E2EE demo | Shows ciphertext-only relay, AEAD, and lab warnings |
| Future full DH ratchet | Shows target PCS behavior when complete message-flow rekeying is added |

## Measurement Rules

- Define expected results before running each experiment.
- Record actual results even if they are worse than expected.
- Keep metrics numeric where possible.
- Use screenshots as evidence, but keep raw JSON/log output too.
- Mention the exact environment: Python version, browser, OS, and demo data size.
- Do not claim production-grade security from a course prototype.

## Experiment Records

Each experiment folder should eventually contain:

```text
README.md
run script or manual steps
input fixture or setup notes
expected-result.md
actual-result.md
raw-output file
screenshot folder if UI evidence is needed
```

The current repository does not keep empty experiment folders. Add a dedicated evidence folder only when real scripts, screenshots, or raw outputs exist.

## Initial Metrics

| Metric | Why it matters |
|---|---|
| Login latency | Auth should remain usable with Argon2id |
| JWT verification time | Measures auth overhead |
| WebSocket connect/auth latency | Affects chat startup |
| Encrypt time per message | Measures browser crypto cost |
| Decrypt time per message | Measures recipient-side crypto cost |
| DH rekey metric | Explains PCS recovery point |
| Ciphertext overhead | Shows packet-size cost of E2EE metadata |
| Server relay latency | Shows ciphertext relay cost |
