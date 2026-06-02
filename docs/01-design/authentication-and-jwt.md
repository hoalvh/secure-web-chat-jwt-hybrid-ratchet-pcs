# JWT Authentication Design

This document describes the account authentication layer.

## Goals

- Authenticate users to the server.
- Bind an authenticated session to a device identifier.
- Authorize REST API and WebSocket access.
- Keep JWT separate from E2EE message encryption.

## Planned Design

- Passwords are hashed with Argon2id.
- Access JWTs are short-lived.
- Refresh tokens are opaque random values stored in HttpOnly cookies.
- Refresh tokens are hashed in the database.
- Logout revokes the refresh session.
- WebSocket authentication is performed with an auth frame after connection establishment.

## Important Distinction

JWT proves account/session identity to the server. It does not decrypt messages and does not replace cryptographic identity keys.

## Scope

Authentication is included so the chat system has real user sessions and device ownership. JWT is a supporting layer; encrypted messages still depend on client-side keys and ratchet state.

The auth layer should be secure and usable:

- Passwords are hashed with Argon2id.
- Access tokens are short-lived.
- Refresh tokens are revocable.
- WebSocket access is authenticated.
- Device IDs are bound to authenticated sessions.

The MVP does not include a full identity platform. The following can remain future work:

- Multi-factor authentication.
- OAuth/social login.
- Admin dashboard.
- Complex role-based access control.
- Enterprise account management.
- Full account recovery workflow.

## Technology Decisions

| Decision | Choice | Reason |
|---|---|---|
| Password hashing | Argon2id | Passwords need a modern memory-hard password hashing scheme; normal hashes such as SHA-256 are not suitable for password storage |
| Access session | Short-lived JWT | The server can verify normal API/WebSocket access without a database lookup on every request |
| Refresh session | Opaque refresh token in HttpOnly cookie | Refresh sessions remain revocable and the long-lived token is not directly readable from normal JavaScript |
| Refresh storage | Hashed token in database | A database leak should not immediately reveal usable refresh tokens |
| JWT library | `jose` | JWT/JWS handling should rely on a standard library instead of manual signing or parsing |
| Backend framework | Fastify | Route-level schemas and a lightweight API layer fit auth/device/key endpoints well |

## JWT Boundary

The system needs account login, API authorization, and WebSocket authorization.

JWT answers this question:

```text
Is this browser session allowed to talk to the server as user Alice and device Alice-1?
```

JWT does not answer this question:

```text
Can this browser session decrypt Bob's encrypted message?
```

That second question is answered only by local device keys and ratchet state.

## Token Strategy

The planned token model is:

- Access JWT lifetime: short.
- Refresh token lifetime: longer but revocable.
- Access JWT storage: browser memory where practical.
- Refresh token storage: HttpOnly cookie.
- Refresh token database format: hashed opaque token with session metadata.

Recommended access JWT claims:

| Claim | Purpose |
|---|---|
| `sub` | User/account ID |
| `device_id` | Authenticated device ID |
| `session_id` | Refresh-session binding |
| `jti` | Unique token ID for tracing and optional deny-listing |
| `iat` | Issued-at time |
| `exp` | Expiration time |
| `aud` | Intended API audience |
| `iss` | Issuer identifier |

## Token Storage Note

Long-lived tokens should not be stored in localStorage because a successful XSS attack can read them directly. This project documents XSS as a serious browser-client threat, so the auth design should avoid the easiest token-exfiltration pattern.

Short-lived access JWTs may be kept in memory. Refresh is handled through an HttpOnly cookie.

## Server Session Alternative

Server-side sessions are also valid. JWT is used here because it fits API and WebSocket authorization cleanly. The key boundary remains the same: JWT authorizes server access, while ciphertext decryption requires local device keys.

## WebSocket Authentication

The WebSocket should authenticate using an explicit auth frame after the connection is established:

```json
{
  "type": "auth",
  "access_token": "jwt..."
}
```

Notes:

- It avoids putting tokens in URL query strings, which can leak through logs or browser history.
- It keeps the WebSocket protocol easy to inspect in the Security Lab.
- It lets the server close unauthenticated sockets cleanly.

## Security Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Password database leak | Offline password guessing | Argon2id with salt and documented parameters |
| Stolen access JWT | Temporary server impersonation | Short lifetime, device claim, no plaintext access without local keys |
| Stolen refresh token | Long-lived session takeover | HttpOnly cookie, hashed storage, revocation on logout |
| XSS | Token/key/state theft from browser | Strict frontend hygiene, no localStorage tokens, document limitation clearly |
| CSRF on refresh endpoint | Silent token refresh abuse | SameSite cookies and restricted refresh route behavior |

## Implementation Notes

- Keep JWT signing keys outside source control.
- Validate claims, expiration, issuer, and audience on every protected route.
- Treat `device_id` as an authenticated claim, not as a client-provided query parameter.
- Log auth events without logging raw tokens.
- Never use JWT payload contents as proof that a public key is trusted by the user.
