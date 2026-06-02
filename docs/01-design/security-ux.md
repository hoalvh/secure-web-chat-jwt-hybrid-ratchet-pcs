# Security UX

UI/UX in this project is used to show security state clearly.

## Scope Boundary

The UI is not a full messaging product interface. Its main role is to make cryptographic behavior visible during demo and testing.

The MVP UI should be good enough for:

- Login and registration.
- Device setup.
- One-to-one chat.
- Contact/key verification.
- Key-change warnings.
- Replay/tamper/decrypt-failure states.
- Security Lab experiments.

Future work:

- Avatars and profile customization.
- Rich message formatting.
- File attachments.
- Push notifications.
- Global search.
- Advanced accessibility polish beyond the MVP baseline.
- Full responsive product-grade mobile layout.

The priority is security clarity: the demo should show what is encrypted, what is verified, what failed, and when post-compromise recovery occurs.

## Purpose

The interface should help users and evaluators understand:

- Whether a conversation is encrypted.
- Whether a contact key has been verified.
- Whether a key has changed.
- Whether a replay or tamper event was detected.
- Whether a session has rekeyed.
- Whether the system recovered after a DH ratchet event.

## Required States

- `Encrypted`
- `Key verified`
- `Unverified key`
- `Key changed`
- `Message decrypt failed`
- `Replay detected`
- `Tamper detected`
- `Rekey in progress`
- `Rekey complete`
- `Compromised in lab mode`
- `Recovered after DH ratchet`

## Security Lab

Security Lab should visualize ciphertext, attack actions, affected messages, compromise windows, and recovery points.

## UI Stack Decisions

| Decision | Choice | Reason |
|---|---|---|
| UI framework | React | Security state changes map naturally to components and state |
| Language | TypeScript | UI states, packet metadata, and lab results can be typed |
| Build tool | Vite | Fast local iteration for demo screens |
| Styling | Tailwind CSS | Consistent badges, warnings, panels, and lab controls without a large custom CSS system |
| Browser tests | Playwright | Verifies that security warnings and lab states appear in real browser flows |

## Security UX Notes

The protocol can still fail in practice if the interface hides important security information. The UI should expose trust state instead of treating encryption as an invisible background feature.

The interface must answer:

- Is this conversation encrypted?
- Is this contact key verified?
- Did the key change?
- Was a message rejected because of tampering?
- Was a replay detected?
- Did the session rekey?
- Did the lab attacker still have access after DH ratchet recovery?

## Required Components

Planned React components:

| Component | Purpose |
|---|---|
| `SecurityBadge` | Shows encrypted, verified, unverified, or warning state |
| `SafetyNumberModal` | Displays fingerprint/safety number for contact verification |
| `KeyChangeWarning` | Blocks or warns before continuing after identity-key change |
| `DecryptFailureNotice` | Explains that a message failed authentication/decryption |
| `ReplayDetectedNotice` | Shows replay rejection in chat and lab views |
| `RekeyStatus` | Shows rekey progress and completion |
| `LabAttackPanel` | Triggers server compromise, JWT theft, replay, tamper, key substitution, and state compromise |
| `LabTimeline` | Visualizes compromise point, exposed window, and recovery point |
| `MetricCard` | Displays benchmark and experiment metrics |

## Tailwind Usage

Tailwind is used because the visual requirements are mostly state clarity, consistency, and speed of implementation.

The project should still avoid messy UI:

- Use reusable components for repeated states.
- Keep warning colors consistent.
- Avoid mixing many badge styles for the same meaning.
- Make lab results readable in screenshots for the final report.

## Security-State Design Rules

- Never show only color for critical warnings; use text labels too.
- Key-change warnings should be visually stronger than normal notifications.
- A decrypt failure should not expose raw exception details to the user.
- The Security Lab may show technical details, but the normal chat view should stay understandable.
- Verified and unverified states must be visually distinct.
- Recovery after DH ratchet should be visible in the lab timeline.

## Playwright Test Targets

The UI should be tested with browser automation for:

- Register and login flow.
- Device setup appears after first login.
- Safety number modal opens and displays a fingerprint.
- Key-change warning appears after simulated key substitution.
- Tampered message displays a failure state.
- Replayed message is rejected and shown in the lab.
- DH rekey changes the lab status from compromised to recovered.
