# Mô Tả Chi Tiết Dự Án Secure Web Chat

Tài liệu này dùng để chia sẻ cho các thành viên trong nhóm, người phản biện, hoặc người mới đọc repository có thể hiểu dự án đang làm gì, vì sao làm như vậy, chạy như thế nào, và từng phần code liên quan đến mục tiêu bảo mật nào.

Tên dự án:

```text
Secure Web Chat Course Prototype
```

Tên repository:

```text
secure-web-chat-jwt-hybrid-ratchet-pcs
```

Phiên bản mô tả này phản ánh implementation hiện tại trong repository: backend Python FastAPI, frontend HTML/CSS/vanilla JavaScript, Web Crypto API, lưu demo bằng JSON local, có Security Lab để trình diễn các tình huống tấn công.

## 1. Tóm Tắt Ngắn Gọn

Dự án xây dựng một ứng dụng chat một-một có đăng ký, đăng nhập, tạo khóa thiết bị trong trình duyệt, gửi tin nhắn đã mã hóa đầu cuối, và có màn hình Security Lab để chứng minh các claim bảo mật.

Điểm quan trọng nhất:

- Server xác thực user bằng JWT.
- Server chỉ lưu public key, metadata định tuyến, nonce, ciphertext và tag.
- Server không nhận private key.
- Server không nhận plaintext message.
- Trình duyệt mới là nơi tạo khóa, mã hóa, giải mã và giữ ratchet state.
- Tin nhắn được mã hóa bằng AES-GCM.
- Khóa AES-GCM được sinh từ ECDH P-256 và HKDF-SHA256.
- Mỗi message có message key riêng.
- Header của packet được đưa vào AES-GCM associated data để phát hiện sửa metadata.
- Security Lab chứng minh server compromise, stolen JWT, replay, tamper, key substitution và PCS rekey experiment.

Câu mô tả một dòng:

```text
Dự án không chỉ làm một app chat, mà làm một prototype môn Applied Cryptography để chứng minh sự khác nhau giữa JWT authentication và end-to-end encryption, đồng thời demo ECDH, HKDF, AES-GCM, replay/tamper protection và simplified hybrid ratchet.
```

## 2. Dự Án Giải Quyết Vấn Đề Gì?

Một ứng dụng chat thông thường có thể dùng HTTPS/TLS và JWT để bảo vệ đường truyền và xác thực user. Tuy nhiên, nếu backend nhận plaintext message rồi lưu database, server vẫn đọc được nội dung tin nhắn. Khi server bị compromise, attacker có thể xem toàn bộ nội dung chat.

Dự án này đặt câu hỏi:

```text
Nếu server bị xem database hoặc attacker có JWT tạm thời, họ có đọc được nội dung chat không?
```

Câu trả lời mục tiêu của dự án:

```text
Không đọc được plaintext message, vì nội dung đã được mã hóa đầu cuối ở client. Server chỉ thấy ciphertext.
```

Từ đó dự án tách rõ hai khái niệm:

| Khái niệm | Trả lời câu hỏi | Dùng gì trong dự án |
|---|---|---|
| Authentication | User có được phép gọi API/WebSocket không? | Password hash Argon2id, JWT, refresh cookie |
| End-to-end encryption | Server có đọc được tin nhắn không? | ECDH P-256, HKDF-SHA256, AES-GCM |
| Integrity/tamper detection | Packet có bị sửa không? | AES-GCM tag, associated data |
| Replay protection | Packet cũ có bị gửi lại không? | Message counter, packet key tracking |
| Key evolution | Mỗi message có dùng key mới không? | Simplified symmetric ratchet |
| Recovery sau compromise | Sau khi state bị lộ, có thể rekey để bảo vệ message tương lai không? | PCS Security Lab experiment |

## 3. Đây Là Gì Và Không Phải Là Gì?

### 3.1. Đây là gì

Dự án là một course prototype phục vụ môn Applied Cryptography. Mục tiêu chính là có sản phẩm chạy được để giải thích, demo và đo được các khái niệm mật mã:

- Password hashing.
- JWT authentication.
- Device key.
- Public key directory.
- ECDH shared secret.
- HKDF key derivation.
- AES-GCM authenticated encryption.
- Associated data.
- Message counter.
- Replay detection.
- Tamper detection.
- Key-change warning.
- Forward secrecy idea.
- Post-compromise recovery experiment.

### 3.2. Đây không phải là gì

Dự án không phải production messenger.

Dự án không implement full Signal protocol.

Dự án không claim bảo mật ngang Signal, WhatsApp, iMessage, Matrix/MLS.

Dự án chưa giải quyết đầy đủ:

- XSS trong trình duyệt.
- Malicious browser extension.
- Full multi-device sync.
- Key transparency.
- Encrypted backup.
- Full X3DH.
- Full Double Ratchet.
- Group chat/MLS.
- Formal verification.
- Post-quantum cryptography.
- Hardening production deployment.

Khi trình bày cần nói rõ:

```text
Đây là simplified Signal-inspired hybrid ratchet dùng để minh họa môn học, không phải full Signal và không production-ready.
```

## 4. Kiến Trúc Tổng Quan

Luồng hệ thống ở mức cao:

```text
+-------------------+        REST/JWT         +----------------------+
| Alice Web Client  | <---------------------> | FastAPI Server       |
| - Access token    |                         | - Argon2id password  |
| - Device private  |        WebSocket        | - JWT verification   |
| - Ratchet state   | <---------------------> | - Key directory      |
| - E2EE crypto     |                         | - Ciphertext relay   |
+-------------------+                         +----------------------+
          |                                             ^
          | E2EE ciphertext only                        |
          v                                             |
+-------------------+                         +----------------------+
| Bob Web Client    |                         | JSON Demo Store      |
| - Device private  |                         | - users              |
| - Decrypt locally |                         | - public keys only   |
| - Ratchet state   |                         | - encrypted messages |
+-------------------+                         +----------------------+

+-------------------+
| Security Lab UI   |
| - server dump     |
| - stolen JWT      |
| - replay/tamper   |
| - key substitution|
| - PCS metrics     |
+-------------------+
```

Các thành phần chính:

| Thành phần | Vị trí | Vai trò |
|---|---|---|
| Backend | `apps/server/main.py` | API auth, device, key bundle, message relay, lab endpoints |
| Frontend | `apps/web/index.html` | UI đăng nhập, chat và Security Lab |
| Client logic | `apps/web/src/app.js` | Web Crypto, IndexedDB, gửi/nhận/decrypt packet |
| Style | `apps/web/src/styles.css` | Giao diện prototype |
| Tests | `apps/server/tests/test_app.py` | Smoke tests backend/security boundary |
| Runtime data | `data/demo_store.json` | Demo store local, không commit |

## 5. Công Nghệ Đang Dùng

### 5.1. Backend

Backend hiện tại dùng Python + FastAPI.

Lý do chọn:

- Dễ chạy trên máy Windows.
- Code gọn trong một file để teammate dễ đọc.
- Phù hợp demo local.
- FastAPI có REST API, WebSocket và TestClient tiện cho kiểm thử.

Backend không làm crypto nội dung message. Backend chỉ làm:

- Đăng ký user.
- Hash password.
- Đăng nhập.
- Phát JWT.
- Quản lý refresh token demo.
- Lưu public key thiết bị.
- Trả public key bundle.
- Lưu encrypted packet.
- Relay packet qua WebSocket hoặc REST/offline fetch.
- Tự cập nhật chat bằng WebSocket notification và polling fallback mỗi 2.5 giây khi đang mở contact.
- Tạo kết quả Security Lab.

### 5.2. Frontend

Frontend hiện tại dùng HTML + CSS + vanilla JavaScript.

Lý do chọn:

- Đúng hướng MVP trong plan: UI tối thiểu để demo crypto.
- Không cần build React/Vite.
- Mở trực tiếp qua FastAPI static server.
- Người khác đọc code dễ thấy flow crypto.

Frontend làm các việc quan trọng:

- Register/login.
- Giữ session sau F5 bằng `sessionStorage` cho short-lived access token.
- Tạo ECDH P-256 device key trong browser.
- Lưu private key trong IndexedDB.
- Publish public key lên server.
- Fetch public key của contact.
- Tạo shared secret bằng ECDH.
- Derive key bằng HKDF-SHA256.
- Encrypt/decrypt message bằng AES-GCM.
- Check replay packet.
- Hiển thị Security Lab.

### 5.3. Storage

Hiện tại server dùng JSON demo store:

```text
data/demo_store.json
```

File này được ignore khỏi Git.

Nó lưu:

- Users.
- Refresh sessions.
- Devices/public keys.
- Messages/ciphertext packets.
- Security events.

Đây là demo storage để chạy nhanh. Nếu cần production-like hơn, có thể thay bằng PostgreSQL + SQLAlchemy/Prisma sau.

### 5.4. Crypto

Crypto phía client dùng Browser Web Crypto API:

| Mục đích | Thuật toán |
|---|---|
| Key agreement | ECDH P-256 |
| Key derivation | HKDF-SHA256 |
| Message encryption | AES-GCM |
| Fingerprint | SHA-256 của canonical public JWK |
| Nonce | 12 bytes random cho AES-GCM |

## 6. Cấu Trúc Thư Mục Quan Trọng

```text
secure-web-chat-jwt-hybrid-ratchet-pcs/
├── apps/
│   ├── server/
│   │   ├── main.py
│   │   └── tests/
│   │       └── test_app.py
│   └── web/
│       ├── index.html
│       └── src/
│           ├── app.js
│           └── styles.css
├── docs/
│   ├── 00-project/
│   ├── 01-design/
│   └── 02-evaluation/
├── experiments/
├── benchmarks/
├── report/
├── presentation/
├── requirements.txt
├── README.md
└── .env.example
```

Giải thích:

| File/thư mục | Ý nghĩa |
|---|---|
| `apps/server/main.py` | Toàn bộ backend MVP |
| `apps/web/index.html` | Giao diện một trang |
| `apps/web/src/app.js` | Logic UI, API, IndexedDB, Web Crypto |
| `apps/web/src/styles.css` | CSS |
| `apps/server/tests/test_app.py` | Test auth, device key, ciphertext-only, reject plaintext |
| `docs/00-project/` | Tài liệu tổng quan, scope, technology decisions |
| `docs/01-design/` | Tài liệu thiết kế threat model, auth, E2EE, ratchet |
| `docs/02-evaluation/` | Kế hoạch experiment và result template |
| `requirements.txt` | Python dependencies |
| `README.md` | Hướng dẫn chạy nhanh |
| `.env.example` | Biến môi trường mẫu |

## 7. Luồng Chạy Tổng Thể

Một demo chuẩn gồm 7 bước:

1. Chạy server.
2. Register Alice.
3. Register Bob.
4. Alice login và tạo device key local.
5. Bob login và tạo device key local.
6. Alice mở Bob, fetch public key của Bob, encrypt message rồi gửi server.
7. Bob mở Alice, fetch public key của Alice, decrypt message trong browser.

Server chỉ thấy:

```text
sender_user_id
recipient_user_id
message_number
nonce
ciphertext
tag
metadata
```

Server không thấy:

```text
plaintext
private key
message key
chain key
root key
```

## 8. Luồng Đăng Ký Và Đăng Nhập

### 8.1. Register

Endpoint:

```text
POST /auth/register
```

Input:

```json
{
  "username": "alice",
  "password": "pass1234"
}
```

Backend xử lý:

1. Chuẩn hóa username.
2. Kiểm tra username chưa tồn tại.
3. Hash password bằng Argon2id.
4. Lưu user.
5. Tạo refresh session.
6. Tạo access JWT.
7. Set refresh token vào HttpOnly cookie.
8. Trả access token cho frontend.

Điểm bảo mật:

- Không lưu plaintext password.
- Password hash là Argon2id nếu dependency đã cài đúng.
- JWT dùng để gọi API, không dùng để decrypt message.

### 8.2. Login

Endpoint:

```text
POST /auth/login
```

Backend xử lý:

1. Tìm user.
2. Verify password bằng Argon2id.
3. Tạo refresh session mới.
4. Phát access JWT.
5. Ghi event `USER_LOGIN`.

### 8.3. JWT claims

JWT chứa các thông tin chính:

```text
sub        user id
username   username
session_id refresh session binding
jti        token id
iat        issued at
exp        expiration
iss        issuer
aud        audience
```

JWT trả lời câu hỏi:

```text
Browser session này có được phép gọi API như Alice không?
```

JWT không trả lời câu hỏi:

```text
Browser session này có decrypt được ciphertext không?
```

Decrypt cần local private key và ratchet/key state.

## 9. Luồng Device Key

Sau khi user login, frontend gọi `ensureDevice()`.

Nếu user chưa có local device key trong IndexedDB:

1. Browser tạo ECDH key pair:

```javascript
crypto.subtle.generateKey(
  { name: "ECDH", namedCurve: "P-256" },
  true,
  ["deriveBits"]
)
```

2. Export public key JWK.
3. Export private key JWK để lưu demo trong IndexedDB.
4. Tính fingerprint:

```text
SHA-256(canonical public JWK)
```

5. Lưu vào IndexedDB theo username.
6. Gửi public key lên server.

Endpoint:

```text
POST /devices
```

Input rút gọn:

```json
{
  "device_id": "alice-browser",
  "device_label": "Browser demo device",
  "public_key_jwk": {
    "kty": "EC",
    "crv": "P-256",
    "x": "...",
    "y": "..."
  },
  "fingerprint": "..."
}
```

Backend kiểm tra:

- Nếu JWK có field `d`, tức private key, thì reject.
- Server chỉ lưu public key.
- Nếu fingerprint của device cũ bị đổi, ghi event `KEY_SUBSTITUTION_WARNING`.

Điểm cần nhớ khi thuyết trình:

```text
Private key không bao giờ gửi lên server. Server chỉ là public key directory.
```

## 10. Luồng Mở Contact Và Lấy Public Key

Khi Alice mở Bob:

1. Alice gọi:

```text
GET /keys/bundle/bob
```

2. Server trả public key bundle của Bob:

```json
{
  "user_id": "bob",
  "device_id": "bob-browser",
  "identity_public_key": {
    "kty": "EC",
    "crv": "P-256",
    "x": "...",
    "y": "..."
  },
  "fingerprint": "..."
}
```

3. Frontend so sánh fingerprint với safety record trong IndexedDB.
4. Nếu lần đầu thấy key, UI hiển thị `Unverified key`.
5. Nếu fingerprint đã biết và không đổi, UI hiển thị `Key verified`.
6. Nếu fingerprint đổi, UI hiển thị `Key changed`.

Ý nghĩa:

- ECDH tự nó không chống MITM nếu public key bị server thay.
- Vì vậy UI cần safety number/fingerprint/key-change warning.
- Demo hiện tại có key-change lab để minh họa nguy cơ này.

## 11. Luồng Gửi Tin Nhắn Mã Hóa

Khi Alice gửi message cho Bob:

1. Alice có private key local.
2. Alice fetch public key của Bob.
3. Alice tạo shared secret bằng ECDH:

```text
ECDH(Alice private key, Bob public key)
```

4. Alice derive root key bằng HKDF-SHA256:

```text
root_key = HKDF(shared_secret, salt=fingerprint_pair, info="root-from-ecdh")
```

5. Alice tạo header:

```json
{
  "version": 1,
  "conversation_id": "alice__bob",
  "sender_user_id": "alice",
  "sender_device_id": "alice-browser",
  "recipient_user_id": "bob",
  "recipient_device_id": "bob-browser",
  "message_number": 1,
  "ratchet_public_key": "alice-fingerprint"
}
```

6. Alice derive directional chain key:

```text
chain_key = HKDF(
  root_key,
  salt=zero32,
  info="chain:v1:alice__bob:alice->bob"
)
```

7. Alice derive per-message key:

```text
message_key = HKDF(
  chain_key,
  salt=zero32,
  info="message-key:1"
)
```

8. Alice sinh nonce 12 bytes random.
9. Alice encrypt plaintext bằng AES-GCM:

```text
AES-GCM(
  key = message_key,
  nonce = random 12 bytes,
  plaintext = message text,
  associated_data = canonical(header)
)
```

10. Alice gửi packet lên server:

```json
{
  "version": 1,
  "algorithm": "ECDH-P-256+HKDF-SHA256+AES-GCM",
  "header": { "...": "..." },
  "nonce": "...",
  "ciphertext": "...",
  "tag": "..."
}
```

Backend lưu packet này, nhưng không decrypt.

## 12. Luồng Nhận Và Giải Mã Tin Nhắn

Khi Bob nhận message từ Alice:

1. Bob tải packet qua WebSocket hoặc `GET /messages/offline`.
2. Bob đọc header.
3. Bob kiểm tra packet có thuộc về mình không.
4. Bob fetch public key của Alice nếu chưa có.
5. Bob tạo shared secret:

```text
ECDH(Bob private key, Alice public key)
```

6. Bob derive root key giống Alice.
7. Bob derive directional chain key theo chiều Alice -> Bob.
8. Bob derive message key theo `message_number`.
9. Bob dùng AES-GCM decrypt với:

```text
nonce
ciphertext + tag
associated_data = canonical(header)
```

10. Nếu decrypt OK, UI hiển thị plaintext.
11. Nếu decrypt fail, UI hiển thị `Decrypt failed`.
12. Nếu packet key đã seen, lab replay coi là bị reject.

Điểm quan trọng:

```text
Alice và Bob tạo cùng shared secret mà server không biết secret đó.
```

## 13. Packet Format

Packet hiện tại có dạng:

```json
{
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
    "ratchet_public_key": "alice-fingerprint"
  },
  "nonce": "base64url...",
  "ciphertext": "base64url...",
  "tag": "base64url..."
}
```

Header được đưa vào associated data. Nghĩa là attacker không thể sửa:

- Sender.
- Recipient.
- Device ID.
- Conversation ID.
- Message number.
- Ratchet public key fingerprint.

Nếu sửa, AES-GCM tag verification fail.

## 14. Key Schedule Và Simplified Ratchet

### 14.1. Root key

Root key được sinh từ ECDH shared secret:

```text
root_key = HKDF(shared_secret, salt=fingerprint_pair, info="root-from-ecdh")
```

Salt dùng fingerprint của hai public key, sort theo thứ tự ổn định. Mục đích là Alice và Bob derive cùng root key dù ai là sender.

### 14.2. Directional chain key

Mỗi hướng gửi có chain khác nhau:

```text
Alice -> Bob
Bob -> Alice
```

Info HKDF có dạng:

```text
chain:v1:{conversation_id}:{sender}->{recipient}
```

Ví dụ:

```text
chain:v1:alice__bob:alice->bob
chain:v1:alice__bob:bob->alice
```

Điều này tránh dùng cùng message key cho hai chiều.

### 14.3. Message key

Mỗi message number có message key riêng:

```text
message_key_i = HKDF(chain_key_i, "message-key:i")
```

Nếu `message_number > 1`, code tiến chain key:

```text
chain_key_{i+1} = HKDF(chain_key_i, "next-chain-key:i")
```

Ý nghĩa:

- Message 1, 2, 3 không dùng cùng AES key.
- Đây là simplified symmetric ratchet.
- Demo phù hợp để giải thích per-message key evolution.

### 14.4. DH ratchet và PCS trong bản hiện tại

Bản hiện tại chưa implement full Double Ratchet. Security Lab có endpoint:

```text
POST /lab/state-compromise
```

Endpoint này mô phỏng PCS/rekey metrics:

- Nếu chỉ symmetric ratchet, attacker biết chain key tại message N có thể tính future key cho đến khi có entropy mới.
- Nếu có DH rekey ở message R, attacker không biết private key mới nên không derive được key sau rekey.

Kết quả trả về gồm:

```text
compromise_at_message
rekey_at_message
total_messages
symmetric_only_future_messages_exposed
hybrid_after_rekey_future_messages_exposed
recovery_point
recovered_after_dh_ratchet
```

Cần nói trung thực:

```text
Đây là PCS experiment để minh họa ý tưởng rekey recovery, chưa phải full production PCS.
```

## 15. Backend API Chi Tiết

### 15.1. Health

```text
GET /health
```

Dùng để kiểm tra server đang chạy.

Ví dụ response:

```json
{
  "ok": true,
  "service": "secure-web-chat",
  "password_hasher": "argon2id",
  "users": 0,
  "messages": 0
}
```

### 15.2. Auth API

| Endpoint | Method | Mục đích |
|---|---|---|
| `/auth/register` | POST | Tạo user, hash password, trả JWT |
| `/auth/login` | POST | Verify password, trả JWT |
| `/auth/refresh` | POST | Dùng refresh cookie để lấy access token mới |
| `/auth/logout` | POST | Revoke refresh session |
| `/me` | GET | Lấy user hiện tại từ JWT |

### 15.3. User/device/key API

| Endpoint | Method | Mục đích |
|---|---|---|
| `/users` | GET | Danh sách user khác để mở contact |
| `/devices` | POST | Đăng ký/cập nhật public device key |
| `/devices` | GET | Xem devices của user hiện tại |
| `/keys/bundle/{username}` | GET | Lấy public key bundle của contact |

### 15.4. Message API

| Endpoint | Method | Mục đích |
|---|---|---|
| `/messages` | POST | Gửi encrypted packet |
| `/messages/offline?peer=bob` | GET | Lấy message giữa user hiện tại và peer |
| `/ws` | WebSocket | Auth bằng frame rồi relay encrypted packet |

WebSocket auth frame:

```json
{
  "type": "auth",
  "access_token": "jwt..."
}
```

Không truyền JWT qua query string URL, vì URL có thể bị log.

### 15.5. Security Lab API

| Endpoint | Method | Scenario |
|---|---|---|
| `/lab/messages` | GET | Server compromise database view |
| `/lab/replay` | POST | Chuẩn bị packet cũ để test replay |
| `/lab/tamper` | POST | Tạo packet đã sửa ciphertext để test AES-GCM tag |
| `/lab/key-substitution` | POST | Ghi/key-change warning scenario |
| `/lab/state-compromise` | POST | Mô phỏng PCS/rekey recovery metrics |
| `/lab/events` | GET | Xem security events |

## 16. Data Model Hiện Tại

Vì dùng JSON demo store, model là dictionary/list trong `data/demo_store.json`.

### 16.1. User

```json
{
  "id": "alice",
  "username": "alice",
  "password_hash": "$argon2id$...",
  "created_at": "...",
  "updated_at": "..."
}
```

Không có plaintext password.

### 16.2. Refresh session

```json
{
  "id": "session-id",
  "user_id": "alice",
  "refresh_token_hash": "sha256-hex",
  "created_at": "...",
  "expires_at": 1234567890,
  "revoked_at": null
}
```

Refresh token thật nằm trong HttpOnly cookie. Database/demo store chỉ lưu hash.

### 16.3. Device

```json
{
  "id": "alice-browser",
  "user_id": "alice",
  "device_label": "Browser demo device",
  "identity_public_key": {
    "kty": "EC",
    "crv": "P-256",
    "x": "...",
    "y": "..."
  },
  "fingerprint": "...",
  "created_at": "...",
  "last_seen_at": "...",
  "revoked_at": null
}
```

Không có private key.

### 16.4. Message

```json
{
  "id": "msg_...",
  "sender_user_id": "alice",
  "recipient_user_id": "bob",
  "packet": {
    "version": 1,
    "algorithm": "ECDH-P-256+HKDF-SHA256+AES-GCM",
    "header": {},
    "nonce": "...",
    "ciphertext": "...",
    "tag": "..."
  },
  "server_received_at": "...",
  "delivered_at": null
}
```

Không có plaintext.

### 16.5. Security event

```json
{
  "id": "evt_...",
  "type": "SERVER_COMPROMISE_VIEWED",
  "actor_user_id": "alice",
  "detail": {},
  "created_at": "..."
}
```

Dùng để ghi các hoạt động lab.

## 17. Security Lab Giải Thích Chi Tiết

Security Lab là phần quan trọng để biến lý thuyết thành evidence.

### 17.1. Server DB

Button UI:

```text
Server DB
```

Endpoint:

```text
GET /lab/messages
```

Mục tiêu:

```text
Chứng minh server/database không có plaintext message.
```

Expected result:

```json
{
  "plaintext": null,
  "plaintext_exposed": false,
  "ciphertext": "...",
  "nonce": "...",
  "tag": "..."
}
```

Ý nghĩa khi trình bày:

```text
Nếu attacker xem database server, attacker chỉ thấy ciphertext và metadata. Nội dung tin nhắn vẫn cần private key/ratchet state ở client để decrypt.
```

### 17.2. Stolen JWT

Button UI:

```text
Stolen JWT
```

Mục tiêu:

```text
Chứng minh JWT compromise khác với E2EE key compromise.
```

Expected result:

```text
Attacker có JWT có thể gọi API tạm thời và lấy ciphertext.
Attacker không decrypt được message nếu không có local private key.
```

Thông điệp:

```text
JWT protects server access. E2EE protects message content.
```

### 17.3. Replay

Button UI:

```text
Replay
```

Mục tiêu:

```text
Chứng minh packet cũ không nên được xử lý lại như message mới.
```

Cách demo:

1. Lab lấy packet message gần nhất.
2. Client kiểm tra packet key:

```text
conversation_id:sender:recipient:message_number
```

3. Nếu packet key đã seen, UI báo replay bị reject.

Expected result:

```json
{
  "scenario": "REPLAY_REJECTED",
  "replay_accepted": false
}
```

### 17.4. Tamper

Button UI:

```text
Tamper
```

Mục tiêu:

```text
Chứng minh sửa ciphertext hoặc header sẽ bị AES-GCM phát hiện.
```

Cách demo:

1. Lab lấy packet cũ.
2. Server tạo bản tampered bằng cách flip bit ciphertext.
3. Client thử decrypt.
4. AES-GCM tag verification fail.

Expected result:

```json
{
  "scenario": "TAMPER_REJECTED",
  "tamper_accepted": false
}
```

Thông điệp:

```text
Encryption alone chưa đủ. AEAD như AES-GCM cung cấp confidentiality và integrity.
```

### 17.5. Key substitution

Button UI:

```text
Key change
```

Mục tiêu:

```text
Chứng minh ECDH không tự chống MITM nếu public key directory bị server/attacker thay đổi.
```

Cách demo:

1. Lab giả lập public key của contact bị thay.
2. Client tính fingerprint mới.
3. Nếu fingerprint khác fingerprint đã biết, UI hiển thị `Key changed`.

Expected result:

```json
{
  "scenario": "KEY_SUBSTITUTION_WARNING",
  "key_substitution_warning_shown": true
}
```

Thông điệp:

```text
Public key cần được xác thực bằng fingerprint/safety number/signature/key transparency. MVP hiện tại dùng warning để minh họa.
```

### 17.6. PCS rekey

Button UI:

```text
PCS rekey
```

Mục tiêu:

```text
Minh họa vì sao symmetric ratchet cần DH rekey để có post-compromise recovery.
```

Input demo mặc định:

```text
compromise_at_message = 3
rekey_at_message = 5
total_messages = 8
```

Ý nghĩa:

- Attacker lấy state tại message 3.
- Nếu chỉ symmetric ratchet, attacker có thể derive một số future key.
- Khi DH rekey xảy ra ở message 5, entropy mới được trộn vào.
- Attacker không biết private key mới nên mất khả năng derive key sau recovery point.

Expected result:

```json
{
  "recovered_after_dh_ratchet": true,
  "recovery_point": 5
}
```

## 18. Mapping Với Môn Applied Cryptography

| Chủ đề môn học | Áp dụng trong dự án |
|---|---|
| Confidentiality | Server chỉ lưu ciphertext |
| Integrity | AES-GCM tag phát hiện tamper |
| Authentication | JWT xác thực user với server |
| Hash/password | Argon2id hash password, SHA-256 fingerprint |
| MAC/AEAD | AES-GCM cung cấp authenticated encryption |
| ECDH/ECC | P-256 ECDH tạo shared secret |
| HKDF | Derive root/chain/message key |
| Modes of operation | AES-GCM thay vì ECB/CBC-only |
| Replay attack | Message counter và seen packet key |
| MITM/key substitution | Fingerprint/key-change warning |
| Forward secrecy | Per-message key evolution |
| PCS | DH rekey recovery experiment |

## 19. Cách Chạy Dự Án

Từ root repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:JWT_SECRET="change-this-for-local-demo"
python -m uvicorn apps.server.main:app --host 127.0.0.1 --port 8000 --reload
```

Mở browser:

```text
http://127.0.0.1:8000
```

Account demo đề xuất:

```text
alice / pass1234
bob   / pass1234
```

Nếu muốn reset dữ liệu demo:

```powershell
Remove-Item .\data\demo_store.json -Force
```

Sau đó reload server hoặc để server tự tạo lại store khi start.

## 20. Demo Script Cho Nhóm

Script demo gợi ý khi quay video hoặc thuyết trình:

1. Mở `http://127.0.0.1:8000`.
2. Register user `alice`.
3. Logout.
4. Register user `bob`.
5. Logout.
6. Login `alice`.
7. Bấm refresh contacts nếu Bob chưa hiện.
8. Open Bob.
9. Kiểm tra fingerprint hiển thị.
10. Gửi message:

```text
Hello Bob, this message is encrypted end-to-end.
```

11. Chạy Security Lab -> Server DB.
12. Chỉ ra server chỉ thấy ciphertext.
13. Logout Alice.
14. Login Bob.
15. Open Alice.
16. Refresh messages.
17. Bob đọc được plaintext trong browser.
18. Chạy Replay.
19. Chạy Tamper.
20. Chạy Key change.
21. Chạy PCS rekey.
22. Giải thích kết quả từng lab.

Thông điệp chính khi kết thúc:

```text
JWT giúp server biết ai đang gọi API.
E2EE giúp server không đọc được nội dung message.
AES-GCM giúp phát hiện sửa packet.
Ratchet giúp key thay đổi theo thời gian.
Security Lab chứng minh các claim bằng demo chạy được.
```

## 21. Cách Kiểm Thử

Chạy backend tests:

```powershell
python -m pytest apps/server/tests
```

Các test hiện có kiểm tra:

- Register user.
- Login/auth token path.
- Device public key storage.
- Server không lưu private key.
- Server lưu ciphertext packet.
- Lab dump không expose plaintext.
- Server reject packet có field `plaintext`.

Kiểm tra nhanh server:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
```

Expected:

```json
{
  "ok": true,
  "service": "secure-web-chat",
  "password_hasher": "argon2id"
}
```

## 22. Những Điểm Bảo Mật Cần Nhấn Mạnh

### 22.1. Server không đọc plaintext

Backend có guard reject packet chứa `plaintext`. Điều này tránh việc frontend gửi nhầm nội dung rõ lên server.

### 22.2. Server không giữ private key

Endpoint `/devices` reject public key JWK nếu có field `d`. Trong JWK của EC key, field `d` là private scalar. Nếu có `d`, tức client đang gửi private key, phải reject.

### 22.3. JWT không phải encryption

JWT chỉ là access credential. Có JWT không có nghĩa decrypt được message.

### 22.4. AES-GCM cần nonce riêng

Mỗi encryption sinh nonce 12 bytes random. Với AES-GCM, không được reuse cùng nonce với cùng key. Trong demo, key thay đổi theo message number và nonce random.

### 22.5. Header phải nằm trong AAD

Nếu header không nằm trong AAD, attacker có thể sửa metadata như sender/recipient/message number. Dự án đưa canonical header vào associated data.

### 22.6. Key substitution vẫn là nguy cơ

Nếu server trả public key giả, ECDH vẫn tạo secret với attacker. Vì vậy cần fingerprint/safety number/key-change warning. Demo hiện tại có UI warning.

## 23. Giới Hạn Và Future Work

### 23.1. Giới hạn hiện tại

- JSON demo store, chưa dùng PostgreSQL production.
- Chưa có database migration.
- JWT dùng HMAC secret demo.
- Private key lưu extractable trong IndexedDB để dễ demo.
- Chưa có full multi-device.
- Chưa có full X3DH.
- Chưa có full Double Ratchet.
- Chưa xử lý out-of-order message phức tạp.
- Replay detection hiện ở client/lab, chưa có replay window production-grade.
- PCS là experiment metric, chưa phải DH ratchet hoàn chỉnh trong message flow.
- Chưa có Playwright UI test.
- Chưa có benchmark thực tế trong `benchmarks/results`.
- Chưa có report/screenshot final.

### 23.2. Future work

- Chuyển JSON store sang PostgreSQL.
- Thêm SQLAlchemy model hoặc Prisma schema thực tế.
- Dùng asymmetric JWT signing RS256/EdDSA.
- Dùng WebSocket realtime relay hoàn chỉnh hơn.
- Implement DH ratchet thật trong message flow.
- Thêm skipped-message key handling.
- Thêm safety number modal có xác nhận thủ công.
- Thêm QR/safety number compare.
- Thêm Playwright tests.
- Thêm benchmark encrypt/decrypt/DH rekey.
- Viết final report từ kết quả lab.
- Thêm screenshot evidence.
- Nghiên cứu PQC hybrid KEM như future work.

## 24. Phân Công Gợi Ý Cho Team

| Mảng | Người phụ trách gợi ý | Công việc |
|---|---|---|
| Backend/auth/lab | Backend owner | FastAPI routes, JWT, device/key API, lab endpoints, data model |
| Crypto protocol | Crypto owner | Key schedule, AES-GCM, packet format, ratchet, protocol tests |
| Frontend/security UX | Frontend owner | UI, IndexedDB, chat flow, warnings, lab dashboard |
| Report/evidence | Cả nhóm | Screenshots, experiment result, giải thích limitation |
| Demo/presentation | Cả nhóm | Demo script, slides, phân vai thuyết trình |

Mỗi thành viên nên đọc tối thiểu:

```text
README.md
docs/00-project/project-description-vn.md
apps/server/main.py
apps/web/src/app.js
docs/01-design/e2ee-protocol-design.md
docs/01-design/key-schedule-and-ratchet.md
docs/02-evaluation/experiment-plan.md
```

## 25. Câu Trả Lời Nhanh Khi Bị Hỏi

### 25.1. Project làm gì?

Project làm một web chat một-một có JWT authentication và client-side end-to-end encryption. Server xác thực user và relay ciphertext, còn mã hóa/giải mã diễn ra ở browser.

### 25.2. JWT có bảo vệ nội dung message không?

Không. JWT chỉ xác thực request với server. Nội dung message được bảo vệ bằng E2EE key ở client.

### 25.3. Server có đọc được message không?

Không, nếu client gửi đúng encrypted packet. Server chỉ lưu nonce, ciphertext, tag và metadata.

### 25.4. Dùng crypto gì?

Browser Web Crypto API: ECDH P-256 để tạo shared secret, HKDF-SHA256 để derive key, AES-GCM để mã hóa và xác thực message.

### 25.5. Vì sao không dùng AES-CBC?

AES-CBC chỉ cung cấp confidentiality nếu dùng riêng, không tự bảo vệ integrity. Project dùng AES-GCM vì đây là AEAD, có cả confidentiality và tamper detection.

### 25.6. Hybrid ratchet là gì trong project?

Trong project này, hybrid ratchet là bản đơn giản hóa gồm symmetric ratchet cho per-message key và DH rekey experiment để minh họa post-compromise recovery. Nó không phải full Signal Double Ratchet.

### 25.7. Nếu server thay public key thì sao?

Client có thể thấy fingerprint đổi và hiển thị `Key changed`. Đây là lý do cần safety number/key verification.

### 25.8. Nếu attacker có JWT thì sao?

Attacker có thể gọi API khi token còn hạn, nhưng chỉ lấy được ciphertext. Không có local private key/ratchet state thì không decrypt được plaintext.

### 25.9. Nếu attacker sửa ciphertext thì sao?

AES-GCM tag verification fail, client không hiển thị plaintext.

### 25.10. Có production-ready không?

Không. Đây là prototype cho môn học, dùng để demo concept và experiment. Production cần nhiều lớp hardening hơn.

## 26. Checklist Hoàn Thiện Trước Khi Nộp

Checklist code:

- Backend chạy được bằng `uvicorn`.
- Frontend mở được ở `http://127.0.0.1:8000`.
- Register/login Alice/Bob chạy được.
- Device key tự tạo và publish được.
- Alice gửi encrypted message cho Bob.
- Bob decrypt được message.
- Server DB lab không có plaintext.
- Replay lab reject.
- Tamper lab reject.
- Key change lab hiện warning.
- PCS rekey lab có metrics.
- `pytest apps/server/tests` pass.

Checklist báo cáo:

- Có ảnh login/register.
- Có ảnh chat encrypted.
- Có ảnh server DB chỉ thấy ciphertext.
- Có ảnh replay rejected.
- Có ảnh tamper rejected.
- Có ảnh key changed warning.
- Có ảnh PCS rekey metrics.
- Có bảng API.
- Có bảng crypto choices.
- Có threat model.
- Có limitation rõ ràng.
- Không claim full Signal hoặc production-grade.

## 27. Kết Luận

Dự án Secure Web Chat là một prototype nhỏ nhưng đủ để thể hiện các ý chính của môn Applied Cryptography trong một sản phẩm chạy được:

- Authentication và encryption là hai lớp khác nhau.
- JWT không thay thế E2EE.
- Server có thể relay message mà không đọc nội dung.
- ECDH giúp hai client tạo shared secret qua server.
- HKDF giúp derive key có domain separation.
- AES-GCM bảo vệ cả confidentiality và integrity.
- Message counter và ratchet giúp minh họa key evolution/replay protection.
- Security Lab biến các claim bảo mật thành demo và evidence.

Khi các thành viên khác đọc tài liệu này, mục tiêu là họ có thể hiểu:

- Dự án đang làm gì.
- Vì sao chọn kiến trúc này.
- Mỗi API dùng để làm gì.
- Crypto flow hoạt động ra sao.
- Demo phải chạy theo thứ tự nào.
- Điểm nào đã hoàn thành.
- Điểm nào vẫn là limitation/future work.
