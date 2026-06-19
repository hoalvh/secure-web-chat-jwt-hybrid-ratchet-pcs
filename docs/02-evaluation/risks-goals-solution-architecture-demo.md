# Project Report: Risks, Security Goals, Architectures and Demonstration Results

## Project Overview

Tên project: Secure Web Chat with JWT Authentication, Hybrid Ratchet and Post-Compromise Security.

Mục tiêu của project là xây dựng một prototype chat bảo mật để minh họa sự khác nhau giữa xác thực người dùng và mã hóa đầu cuối. Server dùng JWT để kiểm soát quyền truy cập API, nhưng nội dung tin nhắn được mã hóa và giải mã ở trình duyệt bằng Web Crypto. Server chỉ đóng vai trò đăng nhập, quản lý public key, lưu/relay ciphertext và cung cấp dashboard admin để quan sát dữ liệu thật được lưu ở phía server.

Stack hiện tại:

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Backend | Python FastAPI | Auth, JWT, refresh session, device directory, ciphertext relay, admin dashboard |
| Frontend | HTML, CSS, vanilla JavaScript | Login, user chat, key/fingerprint view, admin dashboard |
| Client crypto | Browser Web Crypto API | ECDH P-256, HKDF-SHA256, AES-GCM, SHA-256 fingerprint |
| Client storage | IndexedDB, sessionStorage | Private device key, safety/fingerprint state, access-token session |
| Server storage | Local JSON demo store | User hash, refresh-token hash, public key, ciphertext packet, events |
| Test/tooling | Pytest, FastAPI TestClient, Node Web Crypto helper | Backend API/security-boundary tests and manual ciphertext decrypt checks |

## 1. Risks to Security Goals

Project phân tích rủi ro theo ba nhóm: storage risks, exchange risks, và process/logic risks. Mỗi rủi ro được nối với một security goal cụ thể để khi demo có thể chứng minh bằng dữ liệu quan sát được.

### 1.1. Storage Risks

Storage risks là nhóm rủi ro liên quan đến dữ liệu được lưu trên server, browser và file store.

| Risk | Mô tả | Security goal | Cách project xử lý |
|---|---|---|---|
| Server store compromise | Attacker đọc được `data/demo_store.json` hoặc dashboard dữ liệu server | Server không được lưu plaintext message và private key | Server chỉ lưu password hash, refresh-token hash, public key, nonce, ciphertext, tag và metadata |
| Password database leak | Attacker lấy được danh sách user và password hash | Không lưu password dạng rõ | Password được hash bằng Argon2id nếu dependency đầy đủ, fallback scrypt chỉ dùng cho dev |
| Refresh token leak từ store | Attacker đọc session store | Không lưu refresh token dạng rõ | Server chỉ lưu SHA-256 hash của refresh token |
| Private key bị upload lên server | Client gửi nhầm private JWK | Private key phải ở browser | `/devices` reject public_key_jwk nếu có field private `d` |
| Browser IndexedDB bị đọc bởi XSS/malware | Script độc trên browser lấy private key hoặc state | Không claim chống full browser compromise | Tài liệu nêu rõ limitation; private key vẫn tốt hơn lưu ở server nhưng không chống được browser đã bị chiếm |
| Private key export để decrypt tay bị commit nhầm | File export chứa `privateKeyJwk.d` | Private key export chỉ dùng tạm, không đưa lên server/git | `.gitignore` bỏ qua `tmp/`, docs nhắc giữ file export ngoài repo |

Security goals từ storage risks:

- SG-S1: Server compromise không làm lộ plaintext message.
- SG-S2: Server không giữ private key của user.
- SG-S3: Password và refresh token không được lưu dạng rõ.
- SG-S4: Admin dashboard chỉ quan sát dữ liệu server đang lưu, không được làm lộ plaintext hoặc private key.

### 1.2. Exchange Risks

Exchange risks là nhóm rủi ro khi dữ liệu đi qua API, WebSocket hoặc public key directory.

| Risk | Mô tả | Security goal | Cách project xử lý |
|---|---|---|---|
| Stolen JWT | Attacker có access token và gọi API như user | JWT chỉ xác thực request, không giải mã message | JWT không chứa private key hoặc message key |
| Message bị đọc trên đường truyền/server relay | Server hoặc attacker thấy packet khi relay | Packet gửi lên server phải là ciphertext | Browser encrypt bằng AES-GCM trước khi `POST /messages` |
| Tamper ciphertext/header | Attacker sửa ciphertext hoặc metadata | Client phải phát hiện sửa đổi | AES-GCM dùng canonical header làm associated data |
| Replay packet cũ | Attacker gửi lại message cũ | Client/lab phải phát hiện duplicate packet | Packet ID dựa trên conversation, sender, recipient, message number |
| Key substitution | Server/middleman thay public key của contact | Người dùng phải thấy fingerprint/key warning | UI hiển thị fingerprint và lưu safety state |
| WebSocket spoof | Kết nối realtime không xác thực | WebSocket phải auth bằng JWT trước khi nhận notify | `/ws` yêu cầu frame `auth` chứa access token hợp lệ |

Security goals từ exchange risks:

- SG-E1: Có JWT không đồng nghĩa với đọc được plaintext.
- SG-E2: Server chỉ relay encrypted packet.
- SG-E3: Sửa ciphertext hoặc header phải làm decrypt fail.
- SG-E4: Public key substitution phải visible qua fingerprint/key-change warning.
- SG-E5: Realtime channel vẫn phải kiểm tra access token.

### 1.3. Process and Logic Risks

Process/logic risks là nhóm rủi ro do lỗi nghiệp vụ, sai thứ tự xử lý hoặc claim bảo mật quá mức.

| Risk | Mô tả | Security goal | Cách project xử lý |
|---|---|---|---|
| Plaintext sent to server by mistake | Frontend gửi field `plaintext` trong packet | Backend phải chặn trước khi lưu | `store_message()` reject packet nếu canonical JSON chứa `plaintext` |
| Sender spoofing | User A gửi packet nhưng header ghi sender là user B | Sender trong packet phải khớp JWT user | Backend check `sender_user_id == actor_user_id` |
| Message gửi đến user không tồn tại | Packet có recipient sai | Server không lưu packet route sai | Backend trả HTTP 404 nếu recipient không tồn tại |
| Admin dashboard bị mở cho user thường | User thường xem hash/ciphertext toàn hệ thống | Dashboard chỉ dành cho admin | `/admin/dashboard` dùng dependency `require_admin` |
| Contact list làm lộ admin account | User thường thấy account admin như contact chat | User chat chỉ nên thấy user thường | `/users` lọc admin khỏi danh sách user thường |
| Claim full Signal/production security | Prototype bị trình bày quá mức | Báo cáo phải nêu rõ giới hạn | Docs ghi đây là course prototype, chưa phải full Signal |

Security goals từ process/logic risks:

- SG-P1: Backend validation phải bảo vệ boundary trước khi lưu dữ liệu.
- SG-P2: Role admin/user phải tách rõ.
- SG-P3: Demo phải trung thực với giới hạn của MVP.
- SG-P4: Các security claim phải có test hoặc demo evidence.

## 2. Solution Architecture

### 2.1. Kiến trúc tổng quan

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
| Peer browser            |                         | JSON demo store          |
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

Điểm quan trọng: JWT chỉ trả lời câu hỏi "ai được gọi server". JWT không trả lời câu hỏi "ai đọc được message". Message chỉ đọc được nếu browser có private device key và derive đúng AES-GCM key.

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

Server-side public key bundle gồm:

- `device_id`
- `user_id`
- `device_label`
- `identity_public_key`
- `fingerprint`
- `created_at`
- `last_seen_at`

Không có private key trong server store.

### 2.4. Message Encryption Architecture

Message flow:

```text
Alice opens Bob
-> GET /keys/bundle/bob
-> Alice imports Bob public key
-> ECDH P-256 derives shared secret
-> HKDF-SHA256 derives root key
-> HKDF derives per-message key
-> AES-GCM encrypts plaintext with canonical header as AAD
-> POST /messages sends header, nonce, ciphertext, tag
-> Server validates and stores encrypted packet
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

Admin dashboard được thêm để phục vụ yêu cầu quan sát dữ liệu thật đang lưu ở server.

```text
Admin login
-> Server returns user.is_admin = true
-> Frontend opens adminPanel instead of user chat
-> GET /admin/dashboard
-> Server checks require_admin
-> Server returns server-side records
-> UI renders tables for hashes, ciphertext, public keys, events
```

Admin dashboard hiển thị:

- User list và password hash.
- Refresh session và refresh token hash.
- Device public keys và fingerprints.
- Stored ciphertext với nonce, ciphertext, tag, route metadata.
- Security events.
- Store path và số lượng record.

Admin dashboard không hiển thị:

- Plaintext message.
- Browser private key.
- Raw refresh token.

## 3. Demonstration Architecture

### 3.1. Demonstration Roles

| Role | Account | Mục đích |
|---|---|---|
| Admin | `admin / pass1234` | Xem server dashboard: hash pass, ciphertext, public key, session hash |
| User A | `alice / pass1234` | Gửi encrypted message |
| User B | `bob / pass1234` | Nhận và decrypt encrypted message trong browser |

Username `admin` là admin mặc định. Có thể đổi danh sách admin bằng env:

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

User screen chỉ còn:

- Contact list.
- Manual open username.
- Fingerprint/key view.
- Conversation.
- Message composer.
- Realtime/sync badge.

User screen không còn admin/server lab panel.

### 3.3. Admin Demonstration Architecture

```text
Login as admin
-> Frontend detects user.is_admin
-> Show admin dashboard
-> GET /admin/dashboard
-> Render server-side data tables
```

Dashboard dùng để chứng minh:

- Server có password hash, không có password rõ.
- Server có refresh-token hash, không có refresh token rõ.
- Server có public key, không có private key.
- Server có ciphertext, nonce, tag, không có plaintext.
- Server có event log cho các hành động quan trọng.

### 3.4. Backend Test Architecture

Pytest dùng FastAPI TestClient để kiểm tra security boundary:

| Test group | Mục tiêu |
|---|---|
| Register/login/device/message/lab flow | Auth, public key registration, ciphertext-only storage |
| Plaintext rejection | Packet chứa plaintext bị reject HTTP 400 |
| Admin dashboard authorization | User thường bị 403, admin xem được dashboard |
| Contact list filtering | User thường không thấy admin account trong contact list |
| Manual decrypt helper | Kiểm tra một ciphertext thật chỉ decrypt được khi có đúng private key browser |

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

Khi môi trường Python/venv đầy đủ, backend test suite hiện có 4 test chính:

```text
test_register_login_device_and_ciphertext_lab_flow
test_server_rejects_plaintext_in_message_packet
test_admin_dashboard_exposes_server_side_demo_records_to_admin_only
test_normal_user_contact_list_hides_admin_accounts
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
| Manual decrypt helper | Stored packet can be checked with correct exported browser private key | Implemented by `scripts/decrypt_message.mjs` |
| JS syntax | Frontend app and decrypt helper parse successfully | Verified by `node --check` |

### 4.5. Discussion

Kết quả demo cho thấy project đạt mục tiêu chính của một secure web chat prototype:

1. Server có thể xác thực và relay message nhưng không cần plaintext.
2. Admin có thể xem rõ dữ liệu server thật sự đang lưu: hash password, hash refresh token, public key và ciphertext.
3. User thường chỉ dùng chức năng chat và xem key/fingerprint, không có quyền xem dashboard server.
4. JWT và E2EE được tách rõ: JWT dùng cho quyền gọi API; browser private key và Web Crypto dùng cho quyền đọc message.
5. Backend có test cho các boundary quan trọng: không lưu plaintext, không mở dashboard admin cho user thường, không đưa admin vào contact list user thường.
6. Có thể kiểm tra độc lập một ciphertext bằng `scripts/decrypt_message.mjs` khi có đúng private key browser, giúp xác nhận thuật toán Web Crypto khớp với packet server lưu.

### 4.6. Limitations

Đây là course prototype, không phải production messenger:

- Chưa phải full Signal implementation.
- Chưa có X3DH, signed prekeys, skipped-message keys hoặc full Double Ratchet.
- PCS hiện được minh họa ở mức concept/lab metric, chưa phải proof của full ratchet.
- Browser compromise, XSS, malware hoặc malicious extension vẫn có thể lấy token/key trong browser.
- JSON store phù hợp demo local, không phải database production.

## Conclusion

Project chứng minh được thông điệp chính:

```text
JWT answers who can call the server.
E2EE answers who can read the message.
The server can store and relay ciphertext without seeing plaintext.
The admin dashboard can inspect server-side hashes and ciphertext without exposing private keys or plaintext.
```
