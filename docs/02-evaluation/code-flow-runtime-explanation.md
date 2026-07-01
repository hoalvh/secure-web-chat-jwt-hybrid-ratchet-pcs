# Code Flow and Runtime Explanation

This document explains, concisely but in detail, how the current code works: where
data lives, the token structure, what the browser stores, what the server stores,
the steps an encrypted chat goes through, and what has been completed.

## 1. Key Files to Read

| File | Role |
|---|---|
| `apps/server/main.py` | Whole FastAPI backend: auth, JWT, refresh token, user/device/message/admin API, WebSocket |
| `apps/server/db.py` | SQLAlchemy layer: models + engine (SQLite/PostgreSQL), backend chosen via `DATABASE_URL` |
| `migrations/` + `alembic.ini` | Alembic migrations managing the schema |
| `apps/web/index.html` | UI shell (Tabler/Bootstrap): login panel, user chat panel, admin dashboard panel |
| `apps/web/src/app.js` | All frontend logic: session restore, IndexedDB, Web Crypto, chat, WebSocket, admin dashboard render |
| `apps/web/src/styles.css` | Thin custom layer over Tabler/Bootstrap (chat bubbles, contacts, key inspector, badges) |
| `apps/server/tests/test_app.py`, `test_db.py` | Backend tests: auth/ciphertext/admin + DB integrity (FK/cascade/conversation/cleanup/severity) |
| `scripts/decrypt_message.mjs` | Node Web Crypto script to manually decrypt one stored ciphertext given the right browser private key |
| `data/secure_chat.db` | Local SQLite database created by the server (deploy uses PostgreSQL via `DATABASE_URL`) |

Overall flow:

```text
Browser UI
-> apps/web/src/app.js
-> REST API / WebSocket
-> apps/server/main.py
-> apps/server/db.py (SQLAlchemy)
-> data/secure_chat.db (SQLite) or PostgreSQL
-> response back to the browser
```

## 2. Data Stored in the Browser

The browser keeps four kinds of state.

### 2.1. JavaScript memory state

In `apps/web/src/app.js`, the `state` object exists only while the tab is open:

```js
{
  token,
  user,
  device,
  contact,
  contactBundle,
  keyBundles,
  packetIds,
  lastMessages,
  adminData,
  ws,
  refreshTimer,
  renderedKey,
  decryptCache
}
```

Meaning:

| Field | Stores | Note |
|---|---|---|
| `token` | Current access JWT | Used for the `Authorization: Bearer ...` header |
| `user` | User public info | Has `id`, `username`, `is_admin`, `created_at` |
| `device` | The user's device-key record in this browser | Includes the private key JWK |
| `contact` | The username being chatted with | e.g. `bob` |
| `contactBundle` | The contact's public key bundle | From `/keys/bundle/{username}` |
| `keyBundles` | Public key bundle cache | In-RAM map, lost on reload |
| `packetIds` | Packet IDs already seen | Used by replay/demo logic |
| `lastMessages` | Currently displayed messages | From `/messages/offline` |
| `adminData` | Admin dashboard data | Only when logged in as admin |
| `ws` | WebSocket connection | Receives new-message notifications |
| `refreshTimer` | 2.5s polling timer | Fallback auto-refresh of the chat |
| `renderedKey` | Signature of the last rendered message list | Skips re-render when nothing changed (anti-flicker) |
| `decryptCache` | Cache of decrypted bodies by packet key | Avoids re-running crypto on re-render |

### 2.2. `sessionStorage`

Key:

```text
secure-chat-session
```

Value:

```json
{
  "token": "<access_jwt>",
  "user": {
    "id": "alice",
    "username": "alice",
    "is_admin": false,
    "created_at": "..."
  }
}
```

Role:

- Keeps the login across F5/tab reload.
- Does not use `localStorage`, so the token is not kept long after the browser session ends.
- On logout, the code calls `clearSession()` to delete this key.

Restore flow:

```text
Page load
-> restoreSession()
-> read sessionStorage
-> call GET /me with the old token
-> if the token is still valid: enter the app
-> if expired/invalid: clear the session and return to login
```

### 2.3. IndexedDB

Database:

```text
secure-web-chat-demo
```

Object stores:

| Store | Key | Stores |
|---|---|---|
| `devices` | `username` | The device key for each user on this browser |
| `safety` | `id` | The trusted fingerprint for each user/contact pair |

Record in `devices`:

```json
{
  "username": "alice",
  "deviceId": "alice-browser",
  "publicKeyJwk": {
    "kty": "EC",
    "crv": "P-256",
    "x": "...",
    "y": "...",
    "ext": true
  },
  "privateKeyJwk": {
    "kty": "EC",
    "crv": "P-256",
    "x": "...",
    "y": "...",
    "d": "...",
    "ext": true
  },
  "fingerprint": "<sha256_hex_of_public_key>",
  "createdAt": "..."
}
```

Important:

- `privateKeyJwk` stays only in the browser's IndexedDB.
- The server must not receive the private field `d`.
- If `/devices` receives a public key JWK containing `d`, the backend returns HTTP 400.

Record in `safety`:

```json
{
  "id": "alice:bob",
  "fingerprint": "<bob_fingerprint_seen_by_alice>",
  "firstSeenAt": "..."
}
```

Role of `safety`:

- On first opening a contact, the browser stores the fingerprint.
- Next time, if the fingerprint changes, the UI shows `Key changed`.

### 2.4. HttpOnly refresh cookie

The server sets the cookie:

```text
secure_chat_refresh=<random_refresh_token>
HttpOnly
SameSite=Lax
Max-Age=604800
```

Important:

- JavaScript cannot read this cookie because of `HttpOnly`.
- The browser sends the cookie automatically on `fetch(..., credentials: "include")`.
- The server does not store the raw refresh token, only its hash in `refresh_sessions`.

## 3. Token Structure

The project has two token types: the access JWT and the refresh token.

### 3.1. Access JWT

The access JWT is created in `issue_tokens()`.

Header:

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

Payload:

```json
{
  "sub": "alice",
  "username": "alice",
  "session_id": "<random_session_id>",
  "jti": "<random_token_id>",
  "iat": 1710000000,
  "exp": 1710000900,
  "iss": "secure-chat-server",
  "aud": "secure-chat-web"
}
```

Signature:

```text
HMAC-SHA256(
  base64url(header) + "." + base64url(payload),
  JWT_SECRET
)
```

Full token:

```text
base64url(header).base64url(payload).base64url(signature)
```

Payload meaning:

| Field | Meaning |
|---|---|
| `sub` | Primary user id |
| `username` | Username |
| `session_id` | Id of the server-side refresh session |
| `jti` | Unique id of the access token |
| `iat` | Issued at |
| `exp` | Expiry, default 900 seconds |
| `iss` | Issuer, must be `secure-chat-server` |
| `aud` | Audience, must be `secure-chat-web` |

The JWT only proves the user may call the API. It contains no private key, no AES key, and cannot decrypt messages.

### 3.2. Refresh token

The refresh token is a random string:

```text
secrets.token_urlsafe(36)
```

The browser receives it via the HttpOnly cookie. The server stores:

```json
{
  "id": "<session_id>",
  "user_id": "alice",
  "refresh_token_hash": "sha256(refresh_token)",
  "created_at": "...",
  "expires_at": 1710604800,
  "revoked_at": null
}
```

On `/auth/refresh`:

```text
Browser sends the cookie
-> server hashes the received refresh token
-> compares with refresh_token_hash in the store
-> if it matches and is not expired: issue a new access JWT
```

## 4. Data Stored on the Server

The server persists data through SQLAlchemy (`apps/server/db.py`). The backend is
chosen by the `DATABASE_URL` env var:

```powershell
# Local (default): SQLite at data/secure_chat.db
$env:SECURE_CHAT_DATA_DIR="E:\some\temp\data"   # change the SQLite file directory
# Deploy: PostgreSQL
$env:DATABASE_URL="postgresql://user:pass@host:5432/db"
```

Tables (with foreign keys + `ON DELETE`):

```text
users             - account + password hash (Argon2id)
refresh_sessions  - refresh-token hash + expiry (expired rows auto-cleaned)
devices           - device public key + fingerprint
conversations     - normalised one-to-one thread (two participants, last_message_at)
messages          - ciphertext packet, with conversation_id / message_number columns
security_events   - log with severity, actor_ip, actor_user_agent
```

The schema is managed by Alembic (`migrations/`); local SQLite also auto-creates
tables on first run. The example records below illustrate the shape of the data
the API returns.

### 4.1. `users`

Example:

```json
{
  "id": "alice",
  "username": "alice",
  "password_hash": "$argon2id$...",
  "is_admin": false,
  "created_at": "...",
  "updated_at": "..."
}
```

Admin rule:

```text
ADMIN_USERNAMES default = "admin"
```

If the username is `admin`, the user is treated as admin.

### 4.2. `refresh_sessions`

Stores the hash of the refresh token, never the raw token:

```json
{
  "id": "<session_id>",
  "user_id": "alice",
  "refresh_token_hash": "<sha256_hex>",
  "created_at": "...",
  "expires_at": 1710604800,
  "revoked_at": null
}
```

### 4.3. `devices`

The server stores only the public key:

```json
{
  "id": "alice-browser",
  "user_id": "alice",
  "device_label": "Browser demo device",
  "identity_public_key": {
    "kty": "EC",
    "crv": "P-256",
    "x": "...",
    "y": "...",
    "ext": true
  },
  "fingerprint": "<sha256_hex>",
  "created_at": "...",
  "last_seen_at": "...",
  "revoked_at": null
}
```

No `privateKeyJwk` field, no `d`.

### 4.4. `conversations` and `messages`

A `conversations` row is created/updated when a message is stored:

```json
{
  "id": "alice__bob",
  "participant_a": "alice",
  "participant_b": "bob",
  "created_at": "...",
  "last_message_at": "..."
}
```

The server stores the encrypted packet:

```json
{
  "id": "msg_...",
  "conversation_id": "alice__bob",
  "sender_user_id": "alice",
  "recipient_user_id": "bob",
  "message_number": 1,
  "packet": {
    "version": 1,
    "algorithm": "ECDH-P-256+HKDF-SHA256+AES-GCM",
    "header": {
      "version": 1,
      "conversation_id": "alice__bob",
      "sender_user_id": "alice",
      "sender_device_id": "alice-browser",
      "recipient_user_id": "bob",
      "recipient_device_id": "bob-browser",
      "message_number": 1,
      "ratchet_public_key": "<alice_fingerprint>"
    },
    "nonce": "<base64url>",
    "ciphertext": "<base64url>",
    "tag": "<base64url>"
  },
  "server_received_at": "...",
  "delivered_at": null
}
```

The server never stores plaintext. If a submitted packet contains the text `plaintext`, the backend rejects it with HTTP 400.

### 4.5. `security_events`

Stores events for the demo/admin:

```json
{
  "id": "evt_...",
  "type": "USER_LOGIN",
  "severity": "info",
  "actor_user_id": "alice",
  "actor_ip": "127.0.0.1",
  "actor_user_agent": "Mozilla/5.0 ...",
  "detail": {
    "username": "alice"
  },
  "created_at": "..."
}
```

Some events:

- `USER_REGISTERED`
- `USER_LOGIN`
- `LOGIN_FAILED`
- `CIPHERTEXT_STORED`
- `ADMIN_DASHBOARD_VIEWED`
- `SERVER_COMPROMISE_VIEWED`
- `REPLAY_PACKET_PREPARED`
- `TAMPER_PACKET_PREPARED`
- `KEY_SUBSTITUTION_WARNING`
- `DH_REKEY_RECOVERED`

## 5. Register/Login Flow

### 5.1. Register

```text
User enters username/password
-> submitAuth("register")
-> POST /auth/register
-> normalize username
-> hash password
-> create user in the database
-> record USER_REGISTERED
-> issue_tokens()
-> return access_token + user
-> set refresh cookie
-> browser saveSession()
-> enterApp()
```

If the username is `admin`:

```text
user.is_admin = true
enterApp() opens adminPanel
```

If a normal user:

```text
user.is_admin = false
enterApp() opens the appPanel chat
```

### 5.2. Login

```text
User enters username/password
-> POST /auth/login
-> server loads the user from the database
-> verify password hash
-> clean up expired refresh sessions
-> record USER_LOGIN (or LOGIN_FAILED)
-> issue_tokens()
-> browser saveSession()
-> enterApp()
```

### 5.3. Logout

```text
logout()
-> POST /auth/logout
-> server marks the refresh session revoked_at
-> delete the refresh cookie
-> frontend closes the WebSocket
-> stop the polling timer
-> clear token/user/device/contact/adminData and caches
-> clear sessionStorage
-> show the login panel
```

## 6. User Chat Flow

### 6.1. Entering the user app

```text
enterApp()
-> if not admin:
   -> show appPanel
   -> ensureDevice()
   -> loadUsers()
   -> connectWebSocket()
   -> startAutoRefresh()
```

### 6.2. Create or reuse the device key

`ensureDevice()`:

```text
IndexedDB get devices[user.id]
-> if absent:
   -> crypto.subtle.generateKey(ECDH P-256)
   -> export publicKeyJwk
   -> export privateKeyJwk
   -> fingerprint = SHA-256(canonical(publicKeyJwk))
   -> save into IndexedDB
-> POST /devices sends only publicKeyJwk + fingerprint
```

Backend `/devices`:

```text
If public_key_jwk has field "d" -> HTTP 400
If device_id belongs to another user -> HTTP 409
If the fingerprint changed -> record KEY_SUBSTITUTION_WARNING
Store the public key bundle in the database
```

### 6.3. Open a contact

`openContact(username)`:

```text
normalize username
-> getKeyBundle(username)
-> GET /keys/bundle/{username}
-> get the contact's public key, signing key, signed pre-key, and fingerprint
-> verify the device signature and signed pre-key signature
-> check the IndexedDB safety record
-> if the fingerprint changed: UI shows "Key changed"
-> if first time: store the fingerprint in safety
-> enable the message input only when the key checks are acceptable
-> refreshMessages({ force: true })
```

### 6.4. Send a message

`sendMessage()`:

```text
Read plaintext from the input
-> encryptPacket(plaintext)
-> POST /messages { packet, store_mode }
-> clear the input
-> refreshMessages()
```

`encryptPacket()`:

```text
if no outbound session exists:
  GET /keys/bundle/{username}?reserve_otp=true
  verify signed pre-key and optional one-time pre-key signatures
  derive X3DH-style session root and create session_id
messageNumber = session send counter + 1
header = route + device + session + message_number metadata
messageKey = deriveSessionMessageKey(rootKey, header)
nonce = random 12 bytes
AES-GCM encrypt plaintext
AAD = canonical(header)
return packet { header, nonce, ciphertext, tag }
```

Crypto detail:

```text
DH1 = sender device identity private x recipient signed pre-key public
DH2 = sender ephemeral private x recipient device identity public
DH3 = sender ephemeral private x recipient signed pre-key public
DH4 = sender ephemeral private x recipient one-time pre-key public, if reserved
-> HKDF-SHA256 with salt from both device fingerprints
-> session root key
-> HKDF directional session chain key
-> HKDF per-message key
-> AES-GCM encrypt
```

### 6.5. Server receives the message

`POST /messages`:

```text
current_user() verifies the JWT
-> store_message(packet, user.id)
-> reject if the packet contains plaintext
-> reject if header.sender_user_id != JWT user
-> reject if the recipient does not exist
-> reject if header/ciphertext/nonce/tag is missing
-> ensure the conversation row exists, insert the message
-> record CIPHERTEXT_STORED
-> WebSocket notify the recipient
```

The server only sees:

```text
sender, recipient, header metadata, nonce, ciphertext, tag
```

The server does not decrypt.

### 6.6. Receive and decrypt a message

`refreshMessages()`:

```text
GET /messages/offline?peer=bob
-> get the messages of the current conversation
-> skip re-render if the message set is unchanged (anti-flicker)
-> for each packet:
   -> use the decrypt cache, or decryptPacket(packet)
   -> render plaintext on success
   -> render "Decrypt failed" on a wrong key/tag/header
-> swap the list in one operation (no empty flash)
```

`decryptPacket()`:

```text
Check the packet belongs to the current user
-> if checkReplay and the packet ID was seen: reject replay
-> fetch the peer public key bundle
-> derive the root key like the sender
-> derive the message key like the sender
-> AES-GCM decrypt ciphertext + tag
-> AAD = canonical(header)
-> if header/ciphertext/tag was modified: decryption fails
```

## 7. WebSocket and Auto-Refresh Flow

When a user enters the chat:

```text
connectWebSocket()
-> open ws://host/ws
-> send { type: "auth", access_token }
-> server verifies the JWT
-> manager.connect(user_id, socket)
-> server replies { type: "auth_ok" }
```

When Alice sends a message to Bob:

```text
POST /messages
-> manager.send("bob", { type: "encrypted_message", message })
-> Bob's browser receives the frame
-> if the contact is open: refreshMessages()
```

There is also a polling fallback:

```text
startAutoRefresh()
-> setInterval every 2500ms
-> if a contact is open: refreshMessages()
```

So F5 does not immediately lose the session, and messages can update even when the WebSocket cannot be reliably observed.

## 8. Manual Decrypt Flow with an External Script

To manually decrypt a stored message, the following inputs are needed:

| Needed | Where from | Note |
|---|---|---|
| `data/secure_chat.db` | Server store (SQLite/PostgreSQL) | Contains the packet, header, nonce, ciphertext, tag, and peer public key |
| Browser device private key | IndexedDB export of the sender or recipient user | The export file must contain `privateKeyJwk.d` |
| The correct message | `--index`, `--message-id`, or `--sender/--recipient/--number` | A wrong message or route fails |
| The correct algorithm | `scripts/decrypt_message.mjs` | Uses P-256 ECDH, HKDF-SHA256, AES-GCM like the frontend |

Commands:

```powershell
node scripts\decrypt_message.mjs --list
node scripts\decrypt_message.mjs --device .\tmp\<exported-device>.json --index 0
```

Inside the script:

```text
Read the server store
-> choose a message
-> read privateKeyJwk from the device JSON
-> find the peer's public key in the device store
-> ECDH P-256 derive shared secret
-> HKDF root/chain/message key with the same labels as the frontend
-> AES-GCM decrypt with nonce + ciphertext + tag + canonical(header)
-> if the key/header/tag is correct: print the plaintext
-> otherwise: report ok=false
```

(The helper currently reads the legacy JSON store and is being updated to read the
SQLite database.) Exported private keys are debug/evidence only and must stay in
`tmp/` or another git-ignored location.

## 9. Admin Dashboard Flow

### 9.1. Becoming an admin

Default:

```text
ADMIN_USERNAMES = "admin"
```

The `admin` user, after register/login, has:

```json
{
  "is_admin": true
}
```

Multiple admins can be configured:

```powershell
$env:ADMIN_USERNAMES="admin,teacher"
```

### 9.2. Frontend admin flow

```text
Login/register succeeds
-> state.user.is_admin === true
-> enterApp()
-> hide appPanel
-> show adminPanel
-> loadAdminDashboard()
-> GET /admin/dashboard
-> render tables
```

Admin dashboard render:

| Section | Data |
|---|---|
| Storage | Store label, counts of users/devices/conversations/messages/sessions/events |
| Users and password hashes | Username, role, password hash, created time |
| Conversations | Participants, created/last-message time |
| Stored ciphertext | Message route, nonce, ciphertext, tag, received time |
| Device public keys | User, device, fingerprint, public key JWK |
| Refresh token hashes | User, session id, refresh-token hash, expiry, revoked |
| Security events | Severity, event type, actor, source (IP/user-agent), time, detail |

### 9.3. Backend admin flow

`GET /admin/dashboard`:

```text
current_user()
-> verify JWT
-> require_admin()
-> if not admin: HTTP 403
-> if admin:
   -> users with password_hash
   -> devices, public key only
   -> conversations
   -> messages, ciphertext only
   -> refresh_sessions, hash only
   -> last 100 security_events
   -> record ADMIN_DASHBOARD_VIEWED
   -> return JSON (with the DB label password-redacted)
```

The admin dashboard does not return:

- Raw passwords.
- Raw refresh tokens.
- Browser private keys.
- Plaintext messages.

## 10. Quick API Map

| API | Caller | Purpose |
|---|---|---|
| `GET /health` | Browser/test | Check the server is running |
| `POST /auth/register` | Login UI | Create user, hash password, issue tokens |
| `POST /auth/login` | Login UI | Verify password, issue tokens |
| `POST /auth/refresh` | Browser/cookie flow | Issue a new access JWT from the refresh cookie |
| `POST /auth/logout` | User/admin UI | Revoke the session and delete the cookie |
| `GET /me` | Session restore | Check the token is still valid |
| `GET /users` | User chat | Get the contact list; normal users do not see admins |
| `POST /devices` | User chat | Publish the public key |
| `GET /devices` | User chat | List the user's own devices |
| `GET /keys/bundle/{username}` | User chat | Get a contact's public key |
| `GET /keys/bundle/{username}?reserve_otp=true` | User chat | Start a new session and atomically reserve one OTP if available |
| `POST /messages` | User chat | Send an encrypted packet |
| `GET /messages/offline?peer=...` | User chat | Get encrypted packets for a peer |
| `GET /admin/dashboard` | Admin | View server-side hashes/ciphertext/public keys/events |
| `WS /ws` | User chat | Realtime new-message notifications |

The `/lab/...` endpoints remain in the backend for demo/security experiments, but the current user UI has been trimmed to chat and key/fingerprint view only.

## 11. What Has Been Completed

### Backend

- A FastAPI app running one local server that serves both the API and the static frontend.
- Register/login with password hashing.
- Access JWT signed with HS256.
- Refresh token via an HttpOnly cookie; the server stores only the hash.
- Session restore via `/me`.
- Logout revokes the refresh session; expired sessions are cleaned up on login/refresh.
- User/admin role: username `admin` is admin by default.
- Admin dashboard API guarded by `require_admin`.
- Normal users get HTTP 403 on the dashboard.
- A normal user's contact list filters out admin accounts.
- Device public key directory.
- Backend rejects private key material in `/devices`.
- Backend rejects packets containing plaintext.
- Backend rejects sender spoofing.
- Ciphertext relay over REST and WebSocket notification.
- SQLAlchemy database (SQLite local / PostgreSQL deploy) with users, sessions, devices, conversations, messages, events; foreign keys + cascade; Alembic migrations; expired-session cleanup; events with severity/IP/user-agent.
- Pytest covers the main boundaries plus database integrity.

### Frontend user

- Login/register UI.
- F5 still restores the session via `sessionStorage` + `/me`.
- Generates an ECDH P-256 device key in the browser.
- Private key stored in IndexedDB, never sent to the server.
- Public key/fingerprint published to the server.
- Contact list and manual open-username.
- Shows fingerprint/key state.
- Encrypts messages with ECDH + HKDF + AES-GCM.
- Decrypts messages in the browser.
- WebSocket notifications and 2.5s polling fallback (chat re-renders only on change).
- User UI limited to chat + key/fingerprint view.

### Frontend admin

- Admin login opens a separate dashboard.
- View password hashes.
- View refresh-token hashes.
- View device public keys.
- View conversations (participants, times).
- View ciphertext/nonce/tag.
- View security events with severity, actor IP, and user-agent.
- Does not show plaintext/private key/raw refresh token.

### Docs/tests

- README updated with the current demo flow.
- A report covering risks/goals/architecture/demo results.
- Backend tests for the admin dashboard and user filtering.
- A manual decrypt helper `scripts/decrypt_message.mjs`.
- The backend test suite now has 9 tests in `apps/server/tests/` (`test_app.py` + `test_db.py`: FK, cascade, conversation, session cleanup, severity).
- Pre-submission checks: `node --check apps/web/src/app.js`, `node --check scripts/decrypt_message.mjs`, and `.\scripts\test.ps1`.

## 12. Current Limitations

- This is a course prototype, not a production secure messenger.
- Not a full Signal protocol.
- X3DH-style identity/pre-key session setup is implemented for the teaching demo, but skipped-message keys and full Double Ratchet are still missing.
- PCS is mostly a lab/concept endpoint, not a production ratchet.
- IndexedDB private keys do not protect against XSS/malware/malicious browser extensions.
- Storage is already a real database (SQLite local / PostgreSQL deploy, Alembic migrations); the main remaining limitations are the crypto core, deployment/CI, rate limiting, and key recovery.
- The access JWT is a hand-written HMAC in the demo; production should use a vetted JWT library and stricter secret management.
- The manual decrypt helper needs a private key exported to a temp file, so it is for demo/evidence only and that file must not be committed.
