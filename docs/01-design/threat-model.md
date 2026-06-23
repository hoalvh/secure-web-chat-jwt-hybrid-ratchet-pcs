# Threat Model

This document defines the security assumptions, protected assets, trust boundaries, and attacker scenarios for the secure web chat project.

## Assets

- User account credentials.
- Access JWTs and refresh sessions.
- Browser device private keys.
- Browser safety/fingerprint state.
- Derived root, chain, and message keys.
- Plaintext messages.
- Ciphertext message packets.
- Public key bundles.
- Security event logs and benchmark results.
- Admin dashboard output.

## Trust Boundaries

- The server is trusted for account routing and availability, but not for message confidentiality.
- The client browser is trusted only while it is not affected by XSS, malware, or malicious extensions.
- The JSON demo store is treated as potentially compromised in the server-compromise experiment.
- Public keys fetched from the server require verification through fingerprints or key-change warnings.

## Attacker Scenarios

- Server compromise.
- Stolen JWT.
- Replay and tamper attacks.
- Key substitution by a malicious server or key directory.
- Temporary client state compromise.
- XSS against the web client.

Each scenario should include attacker capability, expected impact, mitigation, and measurable result.

## Stack Choices That Support the Threat Model

| Threat-model need | Supporting choice | Reason |
|---|---|---|
| Server should not read plaintext | Browser Web Crypto encryption | Plaintext exists only on sender/recipient clients |
| Stolen JWT should not decrypt messages | Separate JWT and device keys | JWT authenticates to server, while E2EE depends on local private keys |
| Public key substitution must be visible | Fingerprint and key-change UI | Users/evaluators can see when a contact key changes |
| Temporary state compromise should be measurable | Symmetric key evolution plus PCS lab metric | Experiments can explain exposure before and after rekey |
| Replay/tamper should be rejected | AES-GCM associated data and packet IDs | Modified packets fail authentication or replay checks |
| Server store compromise should be demonstrable | JSON ciphertext store and admin dashboard | Admin/lab evidence can inspect stored rows and show ciphertext-only data |
| Browser risk should be explicit | IndexedDB threat note and XSS limitation | Browser-side key storage has limits that must be documented |

## Server Trust Boundary

The server is trusted for:

- Account registration and login.
- Refresh-session management.
- Device ownership metadata.
- Public key directory availability.
- Routing and message delivery.

The server is not trusted for:

- Message confidentiality.
- Private key custody.
- Long-term public key honesty without user-visible verification.
- Protection against database/store inspection in the server-compromise experiment.
- Protection against admin visibility of server-side records; the dashboard is intentionally limited to hashes, public keys, ciphertext, and metadata.

The backend therefore focuses on auth, validation, storage, and relay rather than message decryption.

## Browser Threats

Because this is a web application, the browser is part of the trusted computing base. XSS, malware, or malicious extensions can potentially access local keys, access tokens, and ratchet state.

The project mitigates what is realistic for the course scope:

- Do not store long-lived tokens in `localStorage`.
- Keep private keys client-side only.
- Reject private key submissions at the backend.
- Use visible UI state for key verification and key changes.
- Document XSS as an important limitation.
- Use experiments to distinguish server compromise from client compromise.

The project does not claim to solve malicious browser extensions, infected endpoints, or fully compromised clients.

## Evaluation-Oriented Threat Table

| Scenario | Attacker capability | Expected protected property | Evidence to collect |
|---|---|---|---|
| Server compromise | Reads server store and logs | No plaintext messages or private keys visible | Screenshot/log of ciphertext-only rows |
| Stolen JWT | Calls APIs as victim temporarily | Cannot decrypt ciphertext without browser private key | Attempted fetch/decrypt result |
| Replay | Resends old encrypted packet | Duplicate message rejected | Replay accepted/rejected metric |
| Tamper | Modifies ciphertext/header | AES-GCM verification fails | Tamper accepted/rejected metric |
| Key substitution | Server returns fake public key | UI warns about changed/unverified key | Warning screenshot and event log |
| State compromise | Reads current client state | Past messages protected if old keys are erased | Number of past messages exposed |
| Post-compromise recovery | Attacker loses access after compromise | Future messages protected after fresh DH entropy | Compromise window measurement |
