# Experiments

This document tracks the planned security experiments.

## Scope

Experiments are used to check whether the encrypted chat design behaves as expected under controlled attacker scenarios.

Priority work:

- Build the encryption and ratchet core.
- Simulate attacker capabilities.
- Measure exposed messages and compromise windows.
- Compare weaker baselines with the final design.
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

## Tooling Decisions

| Need | Choice | Reason |
|---|---|---|
| Protocol unit tests | Vitest | Fast TypeScript tests for packet validation, key schedule, and replay logic |
| Browser security-flow tests | Playwright | Confirms warnings and lab states appear in the real UI |
| API micro-benchmarks | autocannon | Quick local load checks for Fastify routes |
| Scenario benchmarks | k6 | Scripted benchmark flows with reportable metrics |
| Data storage | `benchmarks/results/` | Keeps raw evidence separate from source code |
| Attack scripts | `experiments/<scenario>/` | Makes each attack reproducible and easy to grade |

## Security Claims to Check

Each security property should have at least one experiment:

| Claim | Experiment |
|---|---|
| Server cannot read plaintext | Server compromise database inspection |
| JWT does not decrypt messages | Stolen JWT fetch-and-decrypt attempt |
| AEAD detects modification | Tamper attack |
| Counters detect duplicate packets | Replay attack |
| Safety UX detects key substitution | Malicious key directory simulation |
| Symmetric ratchet protects past messages | State leak after old keys are erased |
| DH ratchet supports PCS | State leak followed by DH rekey and future-message test |

## Baselines

The experiments should compare at least three variants where possible:

| Variant | Purpose |
|---|---|
| Plain relay baseline | Shows what happens if the server stores readable plaintext |
| Static-key or symmetric-only variant | Shows limitations before DH recovery is added |
| Final hybrid ratchet design | Shows target behavior with DH-based recovery |

The baseline is included for comparison only.

## Measurement Rules

- Every experiment must define expected results before implementation.
- Actual results must be recorded even if they are worse than expected.
- Metrics should be numeric where possible.
- Screenshots are useful, but they should not replace raw result files.
- Experiment scripts should be deterministic enough for another reviewer to rerun.

## Experiment Records

Each experiment folder should eventually contain:

```text
README.md
run script
input fixture or setup notes
expected-result.md
actual-result.md
raw-output file
screenshot folder if UI evidence is needed
```

## Benchmark Metrics

Initial performance metrics:

| Metric | Why it matters |
|---|---|
| Login latency | Auth should remain usable with Argon2id |
| JWT verification time | Measures auth overhead |
| WebSocket connect/auth latency | Affects chat startup |
| Encrypt time per message | Measures client-side crypto cost |
| Decrypt time per message | Measures recipient-side crypto cost |
| DH rekey latency | Measures PCS recovery overhead |
| Ciphertext overhead | Shows packet-size cost of E2EE metadata |
| Throughput | Shows server relay capacity for ciphertext packets |
