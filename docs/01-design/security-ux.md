# Security UX

UI/UX in this project is used to show security state clearly. The interface is not a full messaging product; its main job is to make cryptographic behavior visible during demos, tests, screenshots, and report writing.

## Current UI Scope

The current MVP UI supports:

- Login and registration.
- Device key setup after login.
- Contact selection.
- One-to-one encrypted chat.
- Fingerprint display.
- Key-change warning.
- Replay/tamper/decrypt-failure lab states.
- Security Lab experiments.

Future product work such as avatars, file attachments, push notifications, global search, and production mobile polish is out of scope.

## Purpose

The interface should help users and evaluators understand:

- Whether a conversation is encrypted.
- Whether a contact key is unverified or changed.
- Whether a message failed to decrypt.
- Whether a replay or tamper event was detected.
- Whether the Security Lab shows server-side plaintext exposure or ciphertext-only storage.
- Whether the PCS rekey metric indicates recovery after a compromise point.

## Required States

- `AES-GCM active`
- `ECDH ready`
- `Key verified`
- `Unverified key`
- `Key changed`
- `Decrypt failed`
- `Replay detected`
- `Tamper detected`
- `WS auth ok`
- `DH_REKEY_RECOVERED`

## Current UI Stack Decisions

| Decision | Current choice | Reason |
|---|---|---|
| UI framework | Plain HTML + vanilla JavaScript | No build step; direct Web Crypto and IndexedDB access |
| Styling | `apps/web/src/styles.css` | Small predictable stylesheet for demo screenshots |
| State storage | `sessionStorage` and IndexedDB | Short-lived access token survives refresh; private device key stays client-side |
| Lab output | JSON rendered in `<pre>` | Easy to inspect and paste into report evidence |
| Verification | Manual browser demo plus backend pytest | Browser automation is future work |

React, TypeScript, Tailwind, and Playwright remain reasonable future choices, but they are not required to run the current MVP.

## Current UI Surfaces

| Surface | Purpose |
|---|---|
| Auth panel | Register/login and status messages |
| Topbar | Current session, device badge, refresh/logout |
| Sidebar | Contact list, manual open, fingerprint/trust display |
| Chat panel | Encrypted messages and decrypt failures |
| Security Lab panel | Server DB, stolen JWT, replay, tamper, key change, PCS rekey actions |

## Security-State Design Rules

- Never show only color for critical warnings; use text labels too.
- Key-change warnings should be visually stronger than normal status updates.
- A decrypt failure should not expose sensitive raw keys or plaintext.
- The Security Lab may show technical JSON, but the normal chat view should stay understandable.
- Verified and unverified states must be visually distinct.
- PCS/rekey results should be visible as structured lab output.

## Evidence Targets

The final report should capture:

- Register/login screen.
- Device/fingerprint state.
- Alice sending an encrypted message.
- Bob decrypting the message locally.
- Server DB lab showing ciphertext-only rows.
- Stolen JWT lab showing server access without plaintext decryption.
- Replay rejected.
- Tamper rejected by AES-GCM.
- Key changed warning.
- PCS rekey metric output.

## Future Browser Test Targets

When Playwright or another browser test runner is added, test:

- Register and login flow.
- Device setup after first login.
- Contact fingerprint display.
- Key-change warning after simulated key substitution.
- Tampered packet decrypt failure.
- Replayed packet rejection.
- Security Lab button outputs.
