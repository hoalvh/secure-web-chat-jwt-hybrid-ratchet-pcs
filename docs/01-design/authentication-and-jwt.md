# JWT Authentication Design

This document describes the account authentication layer used by the current FastAPI demo.

## Goals

- Authenticate users to the server.
- Authorize REST API and WebSocket access.
- Keep JWT separate from end-to-end message encryption.
- Keep refresh sessions revocable.
- Avoid storing long-lived access credentials in browser storage.

## Current Implementation

The current backend lives in `apps/server/main.py`.

Implemented behavior:

- Passwords are hashed with Argon2id through `argon2-cffi`.
- A development-only `scrypt` fallback exists if Argon2id is unavailable.
- Access tokens are HMAC-SHA256 JWTs.
- Refresh tokens are opaque random values in an HttpOnly cookie.
- The server stores only a SHA-256 hash of each refresh token.
- Logout revokes matching refresh sessions and deletes the refresh cookie.
- Expired refresh sessions are purged from the database during login/refresh.
- Auth-related security events (register, login, failed login, logout-related, key-substitution, admin view) are recorded with a severity level, the actor IP, and the user-agent.
- WebSocket authentication is performed with an auth frame after the socket opens.
- Username `admin` is treated as admin by default through `ADMIN_USERNAMES`.
- Admin users are routed to the server dashboard; normal users are routed to chat/key inspection.

## Important Distinction

JWT proves account/session identity to the server. It does not decrypt messages and does not prove that a public key belongs to the intended human contact.

JWT answers this question:

```text
Is this browser session allowed to call server APIs as Alice?
```

End-to-end encryption answers this question:

```text
Can this browser decrypt Bob's encrypted message?
```

The second question requires local browser private keys and the message key schedule, not only a JWT.

## Current Token Model

Access JWT:

- Short-lived.
- Signed with `JWT_SECRET` using HMAC-SHA256.
- Sent as `Authorization: Bearer <token>` for protected REST APIs.
- Sent inside the WebSocket auth frame.
- Stored in `sessionStorage` by the current demo so refresh/F5 does not immediately log the user out.

Refresh token:

- Opaque random value.
- Stored in an HttpOnly cookie named by `REFRESH_COOKIE_NAME`.
- Stored server-side only as a SHA-256 hash.
- Revoked on logout.

Current access JWT claims:

| Claim | Purpose |
|---|---|
| `sub` | User/account ID |
| `username` | Username shown by the app |
| `session_id` | Refresh-session binding |
| `jti` | Unique token ID |
| `iat` | Issued-at time |
| `exp` | Expiration time |
| `iss` | Issuer identifier |
| `aud` | Intended API audience |

## Token Storage Note

Long-lived tokens must not be stored in `localStorage`.

The current demo stores only the short-lived access token in `sessionStorage` to make the classroom demo survive a page refresh. On load, the frontend reads `secure-chat-session` and calls `GET /me`; if the token is invalid, it clears the session and returns to login. A stricter build can keep the access token only in memory and rely on the refresh cookie for session renewal.

The refresh token remains hidden from normal JavaScript through the HttpOnly cookie flag.

## WebSocket Authentication

The WebSocket endpoint is `/ws`. The client connects first and then sends:

```json
{
  "type": "auth",
  "access_token": "jwt..."
}
```

This avoids putting tokens in URL query strings, which can leak through logs, browser history, or proxy records.

After authentication, the server can push notification frames such as:

```json
{
  "type": "encrypted_message",
  "message": {}
}
```

The message remains ciphertext; WebSocket authentication does not give the server plaintext access.

## Security Risks and Mitigations

| Risk | Impact | Current mitigation |
|---|---|---|
| Password database leak | Offline password guessing | Argon2id password hashes |
| Stolen access JWT | Temporary server impersonation | Short TTL; JWT still cannot decrypt ciphertext |
| Stolen refresh token | Longer session takeover | HttpOnly cookie, hashed server storage, logout revocation |
| XSS | Token/key/state theft from browser | No long-lived access token in `localStorage`; XSS documented as limitation |
| Token in URL | Leakage through logs/history | WebSocket auth frame instead of query string |
| Server compromise | API access and database read | Message plaintext and private keys should not be stored server-side |

## Implementation Notes

- Keep `JWT_SECRET` outside source control.
- Validate issuer, audience, expiration, and signature on protected routes.
- Do not log raw access or refresh tokens.
- Keep auth events useful but non-sensitive.
- Treat JWT as authorization only; never use JWT contents as proof that a contact key is trusted.
- A JWT alone is not enough for manual decryption; decrypting a stored packet also needs the correct browser device private key and the peer public key from the server store.
- Production work should replace the small hand-written JWT helper with a reviewed JWT library and stronger key-management practices.
