# Project Report: Risks, Security Goals, Architectures and Demonstration Results

## Project Overview

Project name: Secure Web Chat with JWT Authentication, Hybrid Ratchet and Post-Compromise Security.

The goal of the project is to build a secure-chat prototype that illustrates the
difference between user authentication and end-to-end encryption. The server uses
JWT to control API access, but message content is encrypted and decrypted in the
browser with the Web Crypto API. The server only handles login, public-key
management, ciphertext storage/relay, and an admin dashboard for observing the
real data stored on the server side.

Current stack:

| Component | Technology | Role |
|---|---|---|
| Backend | Python FastAPI | Auth, JWT, refresh session, device directory, ciphertext relay, admin dashboard |
| Frontend | Vanilla JavaScript + Tabler/Bootstrap (CDN) | Login, user chat, key/fingerprint view, admin dashboard |
| Client crypto | Browser Web Crypto API | ECDH P-256, HKDF-SHA256, AES-GCM, SHA-256 fingerprint |
| Client storage | IndexedDB, sessionStorage | Private device key, safety/fingerprint state, access-token session |
| Server storage | SQLAlchemy: SQLite (local) / PostgreSQL (deploy), Alembic migrations | User hash, refresh-token hash, public key, conversations, ciphertext packet, events |
| Test/tooling | Pytest, FastAPI TestClient, Node Web Crypto helper | Backend API/security-boundary + database tests, manual ciphertext decrypt checks |

## 1. Risks to Security Goals

Risks are grouped into three categories: storage risks, exchange risks, and
process/logic risks. Each risk is mapped to a concrete security goal so the demo
can prove it with observable data.

### 1.1. Storage Risks

Storage risks concern data stored on the server, in the browser, and in the data store.

| Risk | Description | Security goal | How the project handles it |
|---|---|---|---|
| Server store compromise | Attacker reads the server database (`data/secure_chat.db` or PostgreSQL) or the server-data dashboard | The server must not store plaintext messages, private keys, or client session keys | The server stores only password hashes, refresh-token hashes, public keys, and offline/manual ciphertext packets; live online packets can be relay-only |
| Password database leak | Attacker obtains the user list and password hashes | Do not store passwords in cleartext | Passwords are hashed with Argon2id when the dependency is present; the scrypt fallback is dev-only |
| Refresh token leak from the store | Attacker reads the session store | Do not store refresh tokens in cleartext | The server stores only the SHA-256 hash of each refresh token |
| Private key uploaded to the server | Client mistakenly sends a private JWK | The private key must stay in the browser | `/devices` rejects `public_key_jwk` that contains the private field `d` |
| Browser IndexedDB read by XSS/malware | Malicious script reads the private key or state | No claim of full browser-compromise protection | Documented as a limitation; client-side keys are better than server storage but do not protect a compromised browser |
| Exported private key (for manual decrypt) committed by mistake | An export file contains `privateKeyJwk.d` | Key exports are temporary and must not reach the server/git | `.gitignore` ignores `tmp/`; docs remind keeping exports outside the repo |

Security goals from storage risks:

- SG-S1: Server compromise does not expose plaintext messages.
- SG-S2: The server does not hold user private keys.
- SG-S3: Passwords and refresh tokens are not stored in cleartext.
- SG-S4: The admin dashboard only observes stored server data; it must not expose plaintext or private keys.

### 1.2. Exchange Risks

Exchange risks concern data moving through the API, WebSocket, or public-key directory.

| Risk | Description | Security goal | How the project handles it |
|---|---|---|---|
| Stolen JWT | Attacker holds an access token and calls the API as the user | A JWT only authenticates requests; it does not decrypt messages | The JWT contains no private key or message key |
| Message read in transit / on relay | Server or attacker sees the packet during relay | Packets sent to the server must be ciphertext | The browser encrypts with AES-GCM before `POST /messages` |
| Tamper with ciphertext/header | Attacker modifies ciphertext or metadata | The client must detect modification | AES-GCM uses the canonical header as associated data |
| Replay an old packet | Attacker resends an old message | Client/lab must detect duplicate packets | Packet ID derived from conversation, sender, recipient, message number |
| Key substitution | Server/middleman swaps a contact's public key | The user must see a fingerprint/key warning | The UI shows fingerprints and stores safety state |
| WebSocket spoof | Unauthenticated realtime connection | WebSocket must authenticate with a JWT before receiving notifications | `/ws` requires an `auth` frame with a valid access token |

Security goals from exchange risks:

- SG-E1: Holding a JWT does not mean being able to read plaintext.
- SG-E2: The server only relays encrypted packets.
- SG-E3: Modifying ciphertext or the header must make decryption fail.
- SG-E4: Public-key substitution must be visible via a fingerprint/key-change warning.
- SG-E5: The realtime channel must still verify the access token.

### 1.3. Process and Logic Risks

Process/logic risks come from business-logic errors, wrong processing order, or over-claiming security.

| Risk | Description | Security goal | How the project handles it |
|---|---|---|---|
| Plaintext sent to the server by mistake | Frontend sends a `plaintext` field in the packet | The backend must block it before storage | `store_message()` rejects packets whose canonical JSON contains `plaintext` |
| Sender spoofing | User A sends a packet whose header claims sender is user B | The packet sender must match the JWT user | Backend checks `sender_user_id == actor_user_id` |
| Message to a non-existent user | Packet has a wrong recipient | The server does not store mis-routed packets | Backend returns HTTP 404 if the recipient does not exist |
| Admin dashboard opened to normal users | A normal user views system-wide hashes/ciphertext | The dashboard is admin-only | `/admin/dashboard` uses the `require_admin` dependency |
| Contact list leaks admin accounts | A normal user sees admin accounts as chat contacts | A user should only see normal users | `/users` filters admins out of the normal-user list |
| Claiming full Signal/production security | The prototype is over-presented | The report must state its limits | Docs state this is a course prototype, not full Signal |

Security goals from process/logic risks:

- SG-P1: Backend validation must protect the boundary before storing data.
- SG-P2: Admin/user roles must be clearly separated.
- SG-P3: The demo must be honest about MVP limitations.
- SG-P4: Security claims must have tests or demo evidence.

## 2. Solution Architecture

### 2.1. Overall Architecture

```text
+-------------------------+        REST/JWT         +--------------------------+
| User browser            | <---------------------> | FastAPI server           |
| - Login session token   |                         | - Auth and JWT verify    |
| - IndexedDB private key |        WebSocket        | - Device key directory   |
| - Web Crypto E2EE       | <---------------------> | - Ciphertext relay       |
| - Chat and key view     |                         | - Admin dashboard API    |
+------------+------------+                         +------------+-------------+
             |                                                   |
             | E2EE ciphertext only                              |
             v                                                   v
+------------+------------+                         +------------+-------------+
| Peer browser            |                         | SQLite / PostgreSQL DB   |
| - Own private key       |                         | - password hashes        |
| - Decrypt locally       |                         | - refresh token hashes   |
| - Fingerprint state     |                         | - public keys only       |
+-------------------------+                         | - encrypted packets      |
                                                    | - security events        |
                                                    +--------------------------+
```

### 2.2. Authentication Architecture

Auth flow:

```text
User submits username/password
-> POST /auth/register or POST /auth/login
-> Server normalizes username
-> Server hashes/verifies password
-> Server creates access JWT
-> Server creates refresh token and stores only refresh_token_hash
-> Browser stores access JWT in sessionStorage
-> API calls use Authorization: Bearer <access_token>
```

Key point: a JWT only answers "who may call the server". It does not answer "who
can read the message". A message is readable only if the browser has the private
device key and derives the correct AES-GCM key.

### 2.3. Device and Key Architecture

Device flow:

```text
Browser generates ECDH P-256 key pair
-> Private JWK stored in IndexedDB
-> Public JWK fingerprinted by SHA-256
-> POST /devices sends public JWK and fingerprint
-> Server stores public key bundle only
-> Server rejects key material if JWK contains private field "d"
```

The server-side public key bundle contains:

- `device_id`
- `user_id`
- `device_label`
- `identity_public_key`
- `fingerprint`
- `created_at`
- `last_seen_at`

No private key is stored on the server.

### 2.4. Message Encryption Architecture

Message flow:

```text
Alice opens Bob
-> GET /keys/bundle/bob
-> Alice verifies Bob's device signature and signed pre-key
-> On first send, GET /keys/bundle/bob?reserve_otp=true reserves one OTP if available
-> X3DH-style P-256 DH inputs derive a local session root
-> HKDF-SHA256 derives a session chain and per-message key
-> AES-GCM encrypts plaintext with canonical header as AAD
-> POST /messages sends header, nonce, ciphertext, tag
-> Server validates and live-relays, or stores ciphertext only for offline/manual delivery
-> WebSocket notifies recipient
-> Recipient fetches packet and decrypts locally
```

Packet format:

```text
{
  version,
  algorithm,
  header: {
    version,
    conversation_id,
    sender_user_id,
    sender_device_id,
    recipient_user_id,
    recipient_device_id,
    message_number,
    ratchet_public_key
  },
  nonce,
  ciphertext,
  tag
}
```

Algorithm label:

```text
ECDH-P-256+HKDF-SHA256+AES-GCM
```

### 2.5. Admin Dashboard Architecture

The admin dashboard was added to satisfy the requirement of observing the real
data the server is storing.

```text
Admin login
-> Server returns user.is_admin = true
-> Frontend opens adminPanel instead of user chat
-> GET /admin/dashboard
-> Server checks require_admin
-> Server returns server-side records
-> UI renders tables for hashes, ciphertext, public keys, events
```

The admin dashboard shows:

- User list and password hashes.
- Refresh sessions and refresh-token hashes.
- Device public keys and fingerprints.
- Stored ciphertext with nonce, ciphertext, tag, route metadata.
- Conversations.
- Security events (with severity, actor IP, user-agent).
- Store path and record counts.

The admin dashboard does not show:

- Plaintext messages.
- Browser private keys.
- Raw refresh tokens.

## 3. Demonstration Architecture

### 3.1. Demonstration Roles

| Role | Account | Purpose |
|---|---|---|
| Admin | `admin / pass1234` | View the server dashboard: password hashes, ciphertext, public keys, session hashes |
| User A | `alice / pass1234` | Send an encrypted message |
| User B | `bob / pass1234` | Receive and decrypt the encrypted message in the browser |

Username `admin` is an admin by default. The admin list can be changed with an env var:

```powershell
$env:ADMIN_USERNAMES="admin,teacher"
```

### 3.2. User Demonstration Architecture

```text
Login as alice
-> Browser creates/reuses alice private key in IndexedDB
-> Alice opens bob
-> Browser fetches Bob public key
-> UI shows Bob fingerprint
-> Alice sends message
-> Browser encrypts locally
-> Server stores ciphertext
-> Login as bob
-> Bob opens alice
-> Browser decrypts locally
```

The user screen contains only:

- Contact list.
- Manual open-username.
- Fingerprint/key view.
- Conversation.
- Message composer.
- Realtime/sync badge.

The user screen has no admin/server-lab panel.

### 3.3. Admin Demonstration Architecture

```text
Login as admin
-> Frontend detects user.is_admin
-> Show admin dashboard
-> GET /admin/dashboard
-> Render server-side data tables
```

The dashboard is used to prove:

- The server has password hashes, not cleartext passwords.
- The server has refresh-token hashes, not cleartext refresh tokens.
- The server has public keys, not private keys.
- The server has ciphertext, nonce, tag, not plaintext.
- The server has an event log for important actions.

### 3.4. Backend Test Architecture

Pytest uses the FastAPI TestClient to verify security boundaries:

| Test group | Goal |
|---|---|
| Register/login/device/message/lab flow | Auth, public-key registration, ciphertext-only storage |
| Plaintext rejection | A packet containing plaintext is rejected with HTTP 400 |
| Admin dashboard authorization | Normal users get 403; admins can view the dashboard |
| Contact list filtering | Normal users do not see admin accounts in the contact list |
| Database integrity | Foreign keys, cascade delete, conversation normalisation, expired-session cleanup, event severity/IP |
| Manual decrypt helper | A stored ciphertext decrypts only with the correct browser private key |

## 4. Demonstration Results

### 4.1. Commands Used

Run backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest apps/server/tests
```

Check frontend JavaScript syntax:

```powershell
node --check apps\web\src\app.js
node --check scripts\decrypt_message.mjs
```

Manual decrypt check:

```powershell
node scripts\decrypt_message.mjs --list
node scripts\decrypt_message.mjs --device .\tmp\<exported-device>.json --index 0
```

Run server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.server.main:app --host 127.0.0.1 --port 8000
```

Open app:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/admin
```

### 4.2. Verification Targets

With a complete Python/venv environment, the backend test suite currently has 9 tests (API boundary + DB integrity):

```text
# apps/server/tests/test_app.py (API / security boundaries)
test_register_login_device_and_ciphertext_lab_flow
test_server_rejects_plaintext_in_message_packet
test_admin_dashboard_exposes_server_side_demo_records_to_admin_only
test_normal_user_contact_list_hides_admin_accounts

# apps/server/tests/test_db.py (database integrity)
test_foreign_key_rejects_orphan_message
test_sending_message_normalises_conversation
test_deleting_user_cascades_to_their_data
test_expired_sessions_are_cleaned_up
test_security_events_capture_severity_and_ip
```

JavaScript syntax check:

```text
node --check apps\web\src\app.js
node --check scripts\decrypt_message.mjs
```

Smoke test server:

```text
GET /health
ok = true
service = secure-web-chat
password_hasher = argon2id
database = sqlite
```

Smoke test admin:

```text
POST /auth/login with admin/pass1234
user.is_admin = true

GET /admin/dashboard
users = 3
messages = 0 at smoke-test time
password_hash visible = true
```

Smoke test admin page:

```text
GET /admin
StatusCode = 200
HasAdminPanel = true
Normal user UI remains chat/key-focused
```

### 4.3. Results by Security Goal

| Security goal | Evidence | Result |
|---|---|---|
| SG-S1: Server does not expose plaintext | Admin dashboard message model sets `plaintext: None`, backend rejects packet with plaintext | Passed |
| SG-S2: Server does not store private key | `/devices` rejects private JWK field `d`; admin dashboard shows public key only | Passed |
| SG-S3: Password/refresh token not stored raw | Dashboard shows password hash and refresh-token hash | Passed |
| SG-S4: Admin observes server data only | Dashboard shows hash/ciphertext/public key/events, not plaintext/private key | Passed |
| SG-E1: JWT does not decrypt message | JWT is used only for API auth; decrypt uses IndexedDB private key and Web Crypto | Passed by architecture and flow |
| SG-E2: Server relays encrypted packet only | `POST /messages` stores nonce, ciphertext, tag and metadata | Passed |
| SG-E3: Tamper should fail | AES-GCM tag authenticates ciphertext and canonical header | Supported by design |
| SG-E4: Key substitution visible | UI shows contact fingerprint and key state | Supported by UI |
| SG-E5: WebSocket authenticated | `/ws` requires auth frame with access token | Supported by implementation |
| SG-P1: Backend validation before storage | Plaintext packet test returns HTTP 400 | Passed |
| SG-P2: Admin/user role separation | Non-admin `GET /admin/dashboard` returns HTTP 403 | Passed |
| SG-P3: Honest MVP limitation | README/design docs state prototype is not full Signal | Documented |

### 4.4. Demonstration Result Table

| Demo item | Expected result | Actual verified status |
|---|---|---|
| Register/login users | Access JWT returned, refresh cookie set | Covered by backend test suite |
| Register admin | `admin` has `is_admin = true` | Covered by admin-dashboard flow |
| User chat view | Normal users see chat and key/fingerprint only | Implemented in `appPanel` |
| Admin dashboard view | Admin sees server storage tables | Covered by `/admin/dashboard` flow |
| Non-admin dashboard block | Normal user gets HTTP 403 | Covered by backend test suite |
| Contact list filtering | Normal user does not see admin account | Covered by backend test suite |
| Password storage | Password hash visible, raw password absent | Covered by backend test suite |
| Ciphertext storage | Server stores ciphertext/nonce/tag | Covered by message test case |
| Plaintext guard | Packet containing plaintext rejected | Covered by backend test suite |
| Database integrity | Foreign keys/cascade/conversation/cleanup hold | Covered by `test_db.py` |
| Manual decrypt helper | Stored packet can be checked with correct exported browser private key | Implemented by `scripts/decrypt_message.mjs` |
| JS syntax | Frontend app and decrypt helper parse successfully | Verified by `node --check` |

### 4.5. Discussion

The demo results show the project meets the main goals of a secure-web-chat prototype:

1. The server can authenticate and relay messages without needing plaintext.
2. The admin can clearly see the data the server actually stores: password hashes, refresh-token hashes, public keys, and ciphertext.
3. Normal users only chat and view keys/fingerprints; they cannot access the server dashboard.
4. JWT and E2EE are clearly separated: JWT for API authorization; the browser private key and Web Crypto for the right to read messages.
5. The backend has tests for the important boundaries: no plaintext storage, no admin dashboard for normal users, no admin accounts in a normal user's contact list.
6. A single ciphertext can be checked independently with `scripts/decrypt_message.mjs` given the correct browser private key, confirming that the Web Crypto algorithm matches the packet the server stores.

### 4.6. Limitations

This is a course prototype, not a production messenger:

- Not a full Signal implementation.
- X3DH-style identity/pre-key session setup is implemented for the teaching demo, but skipped-message keys and full Double Ratchet are still missing.
- PCS is currently shown as a concept/lab metric, not a proof of a full ratchet.
- Browser compromise, XSS, malware, or malicious extensions can still read tokens/keys in the browser.
- Storage is already a real database (SQLite local / PostgreSQL deploy, Alembic migrations); the main remaining limitations are the crypto core (full Double Ratchet/PCS) and deployment/CI, not the storage layer.

## Conclusion

The project demonstrates its core message:

```text
JWT answers who can call the server.
E2EE answers who can read the message.
The server can store and relay ciphertext without seeing plaintext.
The admin dashboard can inspect server-side hashes and ciphertext without exposing private keys or plaintext.
```
