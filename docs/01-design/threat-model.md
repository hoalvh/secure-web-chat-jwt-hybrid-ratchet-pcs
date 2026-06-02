# Threat Model

This document defines the security assumptions, protected assets, trust boundaries, and attacker scenarios for the secure web chat project.

## Assets

- User account credentials.
- Access JWTs and refresh sessions.
- Device identity private keys.
- Signed prekey private keys.
- Ratchet state.
- Plaintext messages.
- Ciphertext message packets.
- Public key bundles.
- Security event logs and benchmark results.

## Trust Boundaries

- The server is trusted for account routing and availability, but not for message confidentiality.
- The client browser is trusted only while it is not affected by XSS, malware, or malicious extensions.
- The database is treated as potentially compromised in the server-compromise experiment.
- Public keys fetched from the server require verification through safety numbers or key-change warnings.

## Attacker Scenarios

- Server compromise.
- Stolen JWT.
- Replay and tamper attacks.
- Key substitution by a malicious server.
- Temporary client state compromise.
- XSS against the web client.

Each scenario should include attacker capability, expected impact, mitigation, and measurable result.

## Stack Choices That Support the Threat Model

The stack is selected to make the threat model testable.

| Threat-model need | Supporting choice | Reason |
|---|---|---|
| Server should not read plaintext | Client-side libsodium encryption | Plaintext exists only on sender/recipient clients |
| Stolen JWT should not decrypt messages | Separate JWT and device keys | JWT authenticates to server, while E2EE depends on local private keys |
| Public key substitution must be visible | Safety number and key-change UI | Users/evaluators can see when the server returns a changed identity key |
| Temporary state compromise should be measurable | Symmetric + DH ratchet | Experiments can compare exposure before and after DH rekey |
| Replay/tamper should be rejected | AEAD associated data and counters | Modified packets fail authentication or replay checks |
| Database compromise should be demonstrable | PostgreSQL ciphertext store | Security Lab can inspect database rows and show ciphertext-only storage |
| Browser risk should be explicit | IndexedDB threat note and XSS limitation | Browser-side key storage has limits that must be documented |

## Server Trust Boundary

The server is trusted for:

- Account registration and login.
- Device ownership metadata.
- Public key directory availability.
- Routing and message delivery.

The server is not trusted for:

- Message confidentiality.
- Long-term public key honesty without user verification.
- Protection against database inspection in the server-compromise experiment.

The backend therefore focuses on auth, validation, storage, and relay rather than message decryption.

## Browser Threats

Because this is a web application, the browser is part of the trusted computing base. XSS, malware, or malicious extensions can potentially access local keys and ratchet state.

The project mitigates what is realistic for the course scope:

- Do not store long-lived JWTs in localStorage.
- Keep private keys client-side only.
- Use careful UI state for key verification.
- Document XSS as an important limitation.
- Use experiments to distinguish server compromise from client compromise.

The project does not claim to solve malicious browser extensions, infected endpoints, or fully compromised clients.

## Evaluation-Oriented Threat Table

| Scenario | Attacker capability | Expected protected property | Evidence to collect |
|---|---|---|---|
| Server compromise | Reads database and server logs | No plaintext messages or private keys visible | Screenshot/log of ciphertext-only rows |
| Stolen JWT | Calls APIs as victim temporarily | Cannot decrypt ciphertext without local keys | Attempted fetch/decrypt result |
| Replay | Resends old encrypted packet | Duplicate message rejected | Replay accepted/rejected metric |
| Tamper | Modifies ciphertext/header | AEAD verification fails | Tamper accepted/rejected metric |
| Key substitution | Server returns fake public key | UI warns about changed/unverified key | Warning screenshot and event log |
| State compromise | Reads current ratchet state | Past messages protected after erasure | Number of past messages exposed |
| Post-compromise recovery | Attacker loses access after compromise | Future messages protected after DH rekey | Compromise window measurement |
