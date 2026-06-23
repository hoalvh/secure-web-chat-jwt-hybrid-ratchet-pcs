# Code Flow and Runtime Explanation

File này giải thích ngắn gọn nhưng chi tiết cách code hiện tại hoạt động: dữ liệu nằm ở đâu, token có cấu trúc gì, browser lưu gì, server lưu gì, chat mã hóa đi qua những bước nào, và phần nào đã làm xong.

## 1. File chính cần đọc

| File | Vai trò |
|---|---|
| `apps/server/main.py` | Toàn bộ backend FastAPI: auth, JWT, refresh token, user/device/message/admin API, WebSocket, JSON store |
| `apps/web/index.html` | Khung UI: login panel, user chat panel, admin dashboard panel |
| `apps/web/src/app.js` | Toàn bộ frontend logic: session restore, IndexedDB, Web Crypto, chat, WebSocket, admin dashboard render |
| `apps/web/src/styles.css` | Giao diện user chat và admin dashboard |
| `apps/server/tests/test_app.py` | Test backend cho auth, ciphertext-only storage, admin dashboard permission |
| `scripts/decrypt_message.mjs` | Script Node Web Crypto để decrypt tay một ciphertext đã lưu nếu có đúng private key browser |
| `data/demo_store.json` | File dữ liệu local do server tự tạo khi chạy demo |

Luồng tổng quát:

```text
Browser UI
-> apps/web/src/app.js
-> REST API / WebSocket
-> apps/server/main.py
-> data/demo_store.json
-> response về browser
```

## 2. Dữ liệu lưu ở browser

Browser hiện có 4 loại state khác nhau.

### 2.1. JavaScript memory state

Trong `apps/web/src/app.js`, object `state` chỉ tồn tại khi tab đang mở:

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
  refreshTimer
}
```

Ý nghĩa:

| Field | Lưu gì | Ghi chú |
|---|---|---|
| `token` | Access JWT hiện tại | Dùng cho header `Authorization: Bearer ...` |
| `user` | User public info | Có `id`, `username`, `is_admin`, `created_at` |
| `device` | Device key record của user trong browser | Có cả private key JWK |
| `contact` | Username đang chat | Ví dụ `bob` |
| `contactBundle` | Public key bundle của contact | Lấy từ `/keys/bundle/{username}` |
| `keyBundles` | Cache public key bundle | Map trong RAM, mất khi reload |
| `packetIds` | Packet IDs đã thấy | Dùng cho replay/demo logic |
| `lastMessages` | Messages đang hiển thị | Lấy từ `/messages/offline` |
| `adminData` | Dữ liệu dashboard admin | Chỉ khi login admin |
| `ws` | WebSocket connection | Nhận notify message mới |
| `refreshTimer` | Timer polling 2.5 giây | Fallback tự refresh chat |

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

Vai trò:

- Giữ login khi bấm F5/reload tab.
- Không dùng `localStorage`, nên token không được giữ lâu sau khi đóng browser session.
- Khi logout, code gọi `clearSession()` để xóa key này.

Luồng restore:

```text
Page load
-> restoreSession()
-> đọc sessionStorage
-> gọi GET /me bằng token cũ
-> nếu token còn hợp lệ: vào app
-> nếu token hết hạn/sai: xóa session và quay lại login
```

### 2.3. IndexedDB

Database:

```text
secure-web-chat-demo
```

Object store:

| Store | Key | Lưu gì |
|---|---|---|
| `devices` | `username` | Device key của từng user trên browser này |
| `safety` | `id` | Fingerprint đã tin cho từng cặp user/contact |

Record trong `devices`:

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

Điểm quan trọng:

- `privateKeyJwk` chỉ nằm trong browser IndexedDB.
- Server không được nhận field private `d`.
- Nếu `/devices` nhận public key JWK có field `d`, backend trả HTTP 400.

Record trong `safety`:

```json
{
  "id": "alice:bob",
  "fingerprint": "<bob_fingerprint_seen_by_alice>",
  "firstSeenAt": "..."
}
```

Vai trò của `safety`:

- Lần đầu mở contact, browser lưu fingerprint.
- Lần sau nếu fingerprint đổi, UI báo `Key changed`.

### 2.4. HttpOnly refresh cookie

Server set cookie:

```text
secure_chat_refresh=<random_refresh_token>
HttpOnly
SameSite=Lax
Max-Age=604800
```

Điểm quan trọng:

- JavaScript không đọc được cookie này vì `HttpOnly`.
- Browser tự gửi cookie khi `fetch(..., credentials: "include")`.
- Server không lưu raw refresh token, chỉ lưu hash trong `refresh_sessions`.

## 3. Cấu trúc token

Project có 2 loại token: access JWT và refresh token.

### 3.1. Access JWT

Access JWT được tạo trong `issue_tokens()`.

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

Token đầy đủ:

```text
base64url(header).base64url(payload).base64url(signature)
```

Ý nghĩa payload:

| Field | Ý nghĩa |
|---|---|
| `sub` | User id chính |
| `username` | Username |
| `session_id` | Id phiên refresh session phía server |
| `jti` | Id riêng của access token |
| `iat` | Issued at |
| `exp` | Expiry, mặc định 900 giây |
| `iss` | Issuer phải là `secure-chat-server` |
| `aud` | Audience phải là `secure-chat-web` |

JWT chỉ dùng để chứng minh user được gọi API. JWT không chứa private key, không chứa AES key, không decrypt được tin nhắn.

### 3.2. Refresh token

Refresh token là chuỗi random:

```text
secrets.token_urlsafe(36)
```

Browser nhận qua HttpOnly cookie. Server lưu:

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

Khi gọi `/auth/refresh`:

```text
Browser gửi cookie
-> server hash refresh token nhận được
-> so với refresh_token_hash trong store
-> nếu match và chưa hết hạn: cấp access JWT mới
```

## 4. Dữ liệu lưu ở server

Server dùng `JsonStore` trong `apps/server/main.py`.

File mặc định:

```text
data/demo_store.json
```

Có thể đổi bằng env:

```powershell
$env:SECURE_CHAT_DATA_DIR="E:\some\temp\data"
```

Cấu trúc tổng:

```json
{
  "users": {},
  "refresh_sessions": {},
  "devices": {},
  "messages": [],
  "security_events": []
}
```

### 4.1. `users`

Ví dụ:

```json
{
  "alice": {
    "id": "alice",
    "username": "alice",
    "password_hash": "$argon2id$...",
    "is_admin": false,
    "created_at": "...",
    "updated_at": "..."
  }
}
```

Admin rule:

```text
ADMIN_USERNAMES mặc định = "admin"
```

Nếu username là `admin`, user được xem là admin.

### 4.2. `refresh_sessions`

Lưu hash của refresh token, không lưu raw token:

```json
{
  "<session_id>": {
    "id": "<session_id>",
    "user_id": "alice",
    "refresh_token_hash": "<sha256_hex>",
    "created_at": "...",
    "expires_at": 1710604800,
    "revoked_at": null
  }
}
```

### 4.3. `devices`

Server chỉ lưu public key:

```json
{
  "alice-browser": {
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
}
```

Không có field `privateKeyJwk`, không có `d`.

### 4.4. `messages`

Server lưu encrypted packet:

```json
{
  "id": "msg_...",
  "sender_user_id": "alice",
  "recipient_user_id": "bob",
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

Server không lưu plaintext. Nếu packet gửi lên có chữ `plaintext`, backend reject HTTP 400.

### 4.5. `security_events`

Lưu event phục vụ demo/admin:

```json
{
  "id": "evt_...",
  "type": "USER_LOGIN",
  "actor_user_id": "alice",
  "detail": {
    "username": "alice"
  },
  "created_at": "..."
}
```

Một số event:

- `USER_REGISTERED`
- `USER_LOGIN`
- `CIPHERTEXT_STORED`
- `ADMIN_DASHBOARD_VIEWED`
- `SERVER_COMPROMISE_VIEWED`
- `REPLAY_PACKET_PREPARED`
- `TAMPER_PACKET_PREPARED`
- `KEY_SUBSTITUTION_WARNING`
- `DH_REKEY_RECOVERED`

## 5. Luồng register/login

### 5.1. Register

```text
User nhập username/password
-> submitAuth("register")
-> POST /auth/register
-> normalize username
-> hash password
-> tạo user trong store
-> record USER_REGISTERED
-> issue_tokens()
-> trả access_token + user
-> set refresh cookie
-> browser saveSession()
-> enterApp()
```

Nếu username là `admin`:

```text
user.is_admin = true
enterApp() mở adminPanel
```

Nếu user thường:

```text
user.is_admin = false
enterApp() mở appPanel chat
```

### 5.2. Login

```text
User nhập username/password
-> POST /auth/login
-> server lấy user trong store
-> verify password hash
-> record USER_LOGIN
-> issue_tokens()
-> browser saveSession()
-> enterApp()
```

### 5.3. Logout

```text
logout()
-> POST /auth/logout
-> server mark refresh session revoked_at
-> delete refresh cookie
-> frontend close WebSocket
-> stop polling timer
-> clear token/user/device/contact/adminData
-> clear sessionStorage
-> show login panel
```

## 6. Luồng user chat

### 6.1. Vào app user

```text
enterApp()
-> nếu không phải admin:
   -> show appPanel
   -> ensureDevice()
   -> loadUsers()
   -> connectWebSocket()
   -> startAutoRefresh()
```

### 6.2. Tạo hoặc reuse device key

`ensureDevice()`:

```text
IndexedDB get devices[user.id]
-> nếu chưa có:
   -> crypto.subtle.generateKey(ECDH P-256)
   -> export publicKeyJwk
   -> export privateKeyJwk
   -> fingerprint = SHA-256(canonical(publicKeyJwk))
   -> save vào IndexedDB
-> POST /devices chỉ gửi publicKeyJwk + fingerprint
```

Backend `/devices`:

```text
Nếu public_key_jwk có field "d" -> HTTP 400
Nếu device_id thuộc user khác -> HTTP 409
Nếu fingerprint đổi -> record KEY_SUBSTITUTION_WARNING
Lưu public key bundle vào server store
```

### 6.3. Mở contact

`openContact(username)`:

```text
normalize username
-> getKeyBundle(username)
-> GET /keys/bundle/{username}
-> lấy public key + fingerprint của contact
-> kiểm tra IndexedDB safety record
-> nếu fingerprint đổi: UI "Key changed"
-> nếu lần đầu: lưu fingerprint vào safety
-> enable message input
-> refreshMessages()
```

### 6.4. Gửi message

`sendMessage()`:

```text
Đọc plaintext từ input
-> encryptPacket(plaintext)
-> POST /messages { packet }
-> clear input
-> refreshMessages()
```

`encryptPacket()`:

```text
rootKey = deriveRootKey(contact public key)
messageNumber = nextMessageNumber()
header = route + device + message_number metadata
messageKey = deriveMessageKey(rootKey, header)
nonce = random 12 bytes
AES-GCM encrypt plaintext
AAD = canonical(header)
return packet { header, nonce, ciphertext, tag }
```

Crypto chi tiết:

```text
ECDH P-256 privateKey(local) + publicKey(remote)
-> shared secret
-> HKDF-SHA256 with salt from both fingerprints
-> root key
-> HKDF directional chain key
-> HKDF per-message key
-> AES-GCM encrypt
```

### 6.5. Server nhận message

`POST /messages`:

```text
current_user() verify JWT
-> store_message(packet, user.id)
-> reject nếu packet chứa plaintext
-> reject nếu header.sender_user_id != JWT user
-> reject nếu recipient không tồn tại
-> reject nếu thiếu header/ciphertext/nonce/tag
-> append vào messages
-> record CIPHERTEXT_STORED
-> WebSocket notify recipient
```

Server chỉ thấy:

```text
sender, recipient, header metadata, nonce, ciphertext, tag
```

Server không decrypt.

### 6.6. Nhận và decrypt message

`refreshMessages()`:

```text
GET /messages/offline?peer=bob
-> lấy messages của conversation hiện tại
-> với mỗi packet:
   -> decryptPacket(packet)
   -> render plaintext nếu decrypt thành công
   -> render "Decrypt failed" nếu sai key/tag/header
```

`decryptPacket()`:

```text
Check packet thuộc user hiện tại
-> nếu checkReplay và packet ID đã thấy: reject replay
-> fetch peer public key bundle
-> derive root key giống bên gửi
-> derive message key giống bên gửi
-> AES-GCM decrypt ciphertext + tag
-> AAD = canonical(header)
-> nếu header/ciphertext/tag bị sửa: decrypt fail
```

## 7. Luồng WebSocket và auto refresh

Khi user vào chat:

```text
connectWebSocket()
-> open ws://host/ws
-> send { type: "auth", access_token }
-> server verify JWT
-> manager.connect(user_id, socket)
-> server reply { type: "auth_ok" }
```

Khi Alice gửi message cho Bob:

```text
POST /messages
-> manager.send("bob", { type: "encrypted_message", message })
-> Bob browser nhận frame
-> nếu đang mở contact: refreshMessages()
```

Ngoài WebSocket còn có polling fallback:

```text
startAutoRefresh()
-> setInterval mỗi 2500ms
-> nếu đang mở contact: refreshMessages()
```

Vì vậy F5 không mất session ngay, và message có thể tự cập nhật kể cả khi WebSocket không quan sát được ổn định.

## 8. Luồng decrypt tay bằng script ngoài

Muốn giải mã tay một message đã lưu, cần đủ các dữ liệu sau:

| Cần gì | Lấy ở đâu | Ghi chú |
|---|---|---|
| `data/demo_store.json` | Server JSON store | Chứa packet, header, nonce, ciphertext, tag và public key peer |
| Browser device private key | IndexedDB export của user sender hoặc recipient | File export phải có `privateKeyJwk.d` |
| Đúng message cần decrypt | `--index`, `--message-id`, hoặc `--sender/--recipient/--number` | Sai message hoặc sai route sẽ fail |
| Thuật toán đúng | `scripts/decrypt_message.mjs` | Dùng P-256 ECDH, HKDF-SHA256, AES-GCM giống frontend |

Lệnh:

```powershell
node scripts\decrypt_message.mjs --list
node scripts\decrypt_message.mjs --device .\tmp\<exported-device>.json --index 0
```

Luồng bên trong script:

```text
Đọc server store
-> chọn message
-> đọc privateKeyJwk từ device JSON
-> tìm public key của peer trong store.devices
-> ECDH P-256 derive shared secret
-> HKDF root/chain/message key với label giống frontend
-> AES-GCM decrypt bằng nonce + ciphertext + tag + canonical(header)
-> nếu đúng key/header/tag: in plaintext
-> nếu sai: báo ok=false
```

Private key export chỉ dùng để debug/evidence và phải để trong `tmp/` hoặc nơi bị git ignore.

## 9. Luồng admin dashboard

### 9.1. Điều kiện thành admin

Mặc định:

```text
ADMIN_USERNAMES = "admin"
```

User `admin` khi register/login sẽ có:

```json
{
  "is_admin": true
}
```

Có thể cấu hình nhiều admin:

```powershell
$env:ADMIN_USERNAMES="admin,teacher"
```

### 9.2. Frontend admin flow

```text
Login/register thành công
-> state.user.is_admin === true
-> enterApp()
-> hide appPanel
-> show adminPanel
-> loadAdminDashboard()
-> GET /admin/dashboard
-> render tables
```

Admin dashboard render:

| Section | Dữ liệu |
|---|---|
| Storage | Store path, số users/devices/messages/sessions/events |
| Users and password hashes | Username, role, password hash, created time |
| Stored ciphertext | Message route, nonce, ciphertext, tag, received time |
| Device public keys | User, device, fingerprint, public key JWK |
| Refresh token hashes | User, session id, refresh token hash, expiry, revoked |
| Security events | Event type, actor, time, detail |

### 9.3. Backend admin flow

`GET /admin/dashboard`:

```text
current_user()
-> verify JWT
-> require_admin()
-> nếu không admin: HTTP 403
-> nếu admin:
   -> copy users with password_hash
   -> copy devices public key only
   -> copy messages with ciphertext only
   -> copy refresh_sessions with hash only
   -> copy last 100 security_events
   -> record ADMIN_DASHBOARD_VIEWED
   -> return JSON
```

Admin dashboard không trả:

- Raw password.
- Raw refresh token.
- Browser private key.
- Plaintext message.

## 10. API map nhanh

| API | Ai gọi | Mục đích |
|---|---|---|
| `GET /health` | Browser/test | Kiểm tra server chạy |
| `POST /auth/register` | Login UI | Tạo user, hash password, cấp token |
| `POST /auth/login` | Login UI | Verify password, cấp token |
| `POST /auth/refresh` | Browser/cookie flow | Cấp access JWT mới từ refresh cookie |
| `POST /auth/logout` | User/admin UI | Revoke session và xóa cookie |
| `GET /me` | Session restore | Kiểm tra token còn hợp lệ |
| `GET /users` | User chat | Lấy contact list, user thường không thấy admin |
| `POST /devices` | User chat | Publish public key |
| `GET /devices` | User chat | List device của chính user |
| `GET /keys/bundle/{username}` | User chat | Lấy public key contact |
| `POST /messages` | User chat | Gửi encrypted packet |
| `GET /messages/offline?peer=...` | User chat | Lấy encrypted packets theo peer |
| `GET /admin/dashboard` | Admin | Xem server-side hash/ciphertext/public key/events |
| `WS /ws` | User chat | Notify message mới realtime |

Các `/lab/...` endpoint vẫn còn ở backend cho demo/security experiment, nhưng UI user hiện tại đã được rút gọn, chỉ còn chat và key/fingerprint view.

## 11. Những gì đã làm được

### Backend

- FastAPI app chạy một server local phục vụ cả API và static frontend.
- Register/login với password hashing.
- Access JWT ký bằng HS256.
- Refresh token bằng HttpOnly cookie, server chỉ lưu hash.
- Session restore qua `/me`.
- Logout revoke refresh session.
- User/admin role: username `admin` là admin mặc định.
- Admin dashboard API có `require_admin`.
- User thường bị chặn dashboard với HTTP 403.
- Contact list của user thường lọc admin account.
- Device public key directory.
- Backend reject private key material trong `/devices`.
- Backend reject packet chứa plaintext.
- Backend reject sender spoofing.
- Ciphertext relay qua REST và WebSocket notify.
- JSON demo store có users, sessions, devices, messages, events.
- Pytest kiểm tra các boundary chính.

### Frontend user

- Login/register UI.
- F5 vẫn restore session bằng `sessionStorage` + `/me`.
- Tự tạo ECDH P-256 device key trong browser.
- Private key lưu IndexedDB, không gửi server.
- Public key/fingerprint publish lên server.
- Contact list và manual open username.
- Hiển thị fingerprint/key state.
- Encrypt message bằng ECDH + HKDF + AES-GCM.
- Decrypt message trong browser.
- WebSocket notify và polling fallback 2.5 giây.
- User UI chỉ còn chat + xem key/fingerprint.

### Frontend admin

- Admin login mở dashboard riêng.
- Xem password hash.
- Xem refresh token hash.
- Xem public device key.
- Xem ciphertext/nonce/tag.
- Xem security events.
- Không xem plaintext/private key/raw refresh token.

### Docs/tests

- README đã cập nhật demo flow mới.
- Có report risks/goals/architecture/demo results.
- Có test backend cho admin dashboard và user filtering.
- Có script decrypt tay `scripts/decrypt_message.mjs`.
- Test backend hiện có 4 test chính trong `apps/server/tests/test_app.py`.
- Lệnh kiểm tra nên chạy trước khi nộp: `node --check apps/web/src/app.js`, `node --check scripts/decrypt_message.mjs`, và `.\scripts\test.ps1`.

## 12. Giới hạn hiện tại

- Đây là course prototype, chưa phải production secure messenger.
- Chưa phải full Signal protocol.
- Chưa có X3DH, signed prekeys, skipped-message keys hoặc full Double Ratchet.
- PCS hiện chủ yếu là lab/concept endpoint, chưa phải ratchet production.
- IndexedDB private key không chống được XSS/malware/browser extension độc hại.
- JSON file store chỉ phù hợp demo local, chưa phải DB production.
- Access JWT đang tự implement bằng HMAC trong demo; production nên dùng thư viện JWT chuẩn và cấu hình secret nghiêm túc hơn.
- Script decrypt tay cần export private key ra file tạm, nên chỉ dùng cho demo/evidence và không được commit file đó.

## 13. Câu nhớ nhanh khi thuyết trình

```text
JWT dùng để biết ai được gọi server.
Private key trong IndexedDB dùng để biết ai đọc được message.
Server chỉ lưu hash, public key và ciphertext.
Admin xem được dữ liệu server đang lưu, nhưng không xem được plaintext/private key.
User thường chỉ chat và xem fingerprint/key.
```
