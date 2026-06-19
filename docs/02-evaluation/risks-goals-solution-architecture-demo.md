# Risks, Goals, Solution, Architecture, Demo Result and Commands

Tài liệu này giải thích ngắn gọn và rõ ràng mạch trình bày của dự án:

```text
Risks -> Security Goals -> Solution and Architecture -> Demonstration Architecture -> Demo Results and Commands
```

Nội dung phản ánh stack hiện tại của repository:

- Backend: Python FastAPI.
- Frontend: HTML/CSS/vanilla JavaScript.
- Client crypto: Browser Web Crypto API.
- Thuật toán demo: ECDH P-256, HKDF-SHA256, AES-GCM.
- Client private state: IndexedDB.
- Server storage: JSON demo store trong `data/demo_store.json`.
- Test: Pytest + FastAPI TestClient.

## 1. Risks -> Goals

Project không chỉ làm app chat, mà dùng app chat để chứng minh các claim mật mã. Bảng dưới đây nối từng rủi ro với mục tiêu bảo mật và bằng chứng demo cần có.

| Risk | Vấn đề nếu không xử lý | Security goal | Cách chứng minh trong demo |
|---|---|---|---|
| Server compromise | Attacker đọc database/server store và thấy toàn bộ tin nhắn | Server chỉ lưu ciphertext, không lưu plaintext | Security Lab -> Server DB trả `plaintext: null`, `plaintext_exposed: false` |
| Stolen JWT | Attacker có token và gọi API như user thật | JWT chỉ cấp quyền gọi server, không giải mã message | Security Lab -> Stolen JWT cho thấy attacker lấy được ciphertext nhưng không có browser private key để decrypt |
| Plaintext sent to server | Frontend gửi nhầm nội dung rõ lên backend | Backend phải reject packet có plaintext | Test backend gửi packet có field `plaintext` và nhận HTTP 400 |
| Private key uploaded | Server biết private key, phá vỡ end-to-end encryption | Private key phải ở browser, server chỉ nhận public key | `/devices` reject JWK có field private `d` |
| Tamper attack | Attacker sửa ciphertext hoặc metadata nhưng client vẫn nhận | AES-GCM phải phát hiện sửa đổi | Security Lab -> Tamper tạo packet bị sửa, browser decrypt fail |
| Replay attack | Attacker gửi lại packet cũ như message mới | Client/lab phải phát hiện duplicate packet ID/message counter | Security Lab -> Replay trả expected result `REPLAY_REJECTED` |
| Key substitution | Server/middleman thay public key của contact | UI phải hiển thị fingerprint/key-change warning | Security Lab -> Key change hiển thị warning |
| Client state compromise | Attacker lấy state hiện tại ở client | Cần giải thích forward secrecy và PCS limitation | Security Lab -> PCS rekey metric cho thấy recovery point sau DH rekey |
| XSS/browser compromise | Script độc trong browser đọc token/key/state | Không claim giải quyết hoàn toàn browser compromise | Docs nêu rõ limitation: IndexedDB không chống XSS/malicious extension |

## 2. Security Goals

Các mục tiêu chính của MVP:

| Goal | Ý nghĩa trong project |
|---|---|
| Authentication separated from encryption | JWT xác thực request với server, nhưng không mã hóa hoặc giải mã message |
| Ciphertext-only server | Server lưu user/session/public key/ciphertext/metadata, không lưu plaintext/private key |
| Client-side E2EE | Browser tạo key, derive key, encrypt/decrypt message |
| AEAD integrity | AES-GCM tag phát hiện sửa ciphertext hoặc associated data |
| Per-message key derivation | Mỗi message có key riêng từ HKDF và message number |
| Replay visibility | Packet ID/message counter giúp demo replay rejection |
| Key-substitution visibility | Fingerprint/key-change UI giúp thấy khi contact key đổi |
| PCS explanation | Demo metric giải thích vì sao cần DH rekey để recovery sau compromise |

## 3. Solution and Architecture

### 3.1. Layer chính

| Layer | File chính | Vai trò |
|---|---|---|
| Browser UI | `apps/web/index.html`, `apps/web/src/styles.css` | Màn hình login, chat, Security Lab |
| Browser logic | `apps/web/src/app.js` | Gọi API, tạo key, IndexedDB, encrypt/decrypt, lab actions |
| Backend API | `apps/server/main.py` | Auth, JWT, device/key API, message relay, lab endpoints |
| Backend tests | `apps/server/tests/test_app.py` | Kiểm tra auth, device, ciphertext-only, plaintext rejection |
| Demo store | `data/demo_store.json` | Lưu user, refresh session hash, public key, ciphertext packet, event |

### 3.2. Kiến trúc tổng quát

```text
+------------------------+       REST/JWT        +-------------------------+
| Alice browser          | <-------------------> | FastAPI backend         |
| - sessionStorage token |                      | - Argon2id password     |
| - IndexedDB private key|       WebSocket      | - HMAC-SHA256 JWT       |
| - Web Crypto E2EE      | <-------------------> | - Device/key directory  |
| - Security Lab UI      |                      | - Ciphertext relay      |
+-----------+------------+                      | - Lab endpoints         |
            |                                   +------------+------------+
            | E2EE ciphertext only                           |
            v                                                v
+-----------+------------+                      +------------+------------+
| Bob browser            |                      | JSON demo store         |
| - IndexedDB private key|                      | - password hashes       |
| - Web Crypto decrypt   |                      | - refresh token hashes  |
| - Fingerprint checks   |                      | - public keys only      |
+------------------------+                      | - encrypted packets     |
                                                | - security events       |
                                                +-------------------------+
```

### 3.3. Auth flow

```text
Browser
-> POST /auth/register or POST /auth/login
-> Server verifies password with Argon2id
-> Server returns short-lived JWT
-> Server sets refresh token in HttpOnly cookie
-> Browser sends JWT as Authorization: Bearer <token>
```

Điểm cần nhấn mạnh:

- JWT chỉ chứng minh user được gọi API.
- JWT không chứa private key.
- Có JWT không đồng nghĩa với decrypt được message.

### 3.4. Device/key flow

```text
Browser
-> generate ECDH P-256 key pair by Web Crypto
-> store private JWK in IndexedDB
-> compute public key fingerprint with SHA-256
-> POST /devices with public JWK only
-> Server rejects JWK if it contains private field "d"
```

Backend chỉ lưu:

```text
device_id
user_id
device_label
identity_public_key
fingerprint
timestamps
```

Backend không lưu private key.

### 3.5. Message encryption flow

```text
Alice opens Bob
-> GET /keys/bundle/bob
-> Alice imports Bob public key
-> ECDH P-256 shared secret
-> HKDF-SHA256 root key
-> HKDF directional chain key
-> HKDF per-message AES-GCM key
-> AES-GCM encrypt plaintext with canonical header as AAD
-> POST /messages with nonce, ciphertext, tag, header
-> Server stores and relays encrypted packet only
```

Packet algorithm label:

```text
ECDH-P-256+HKDF-SHA256+AES-GCM
```

Server-side message boundary:

```text
If packet contains plaintext -> reject HTTP 400
If sender_user_id != JWT user -> reject HTTP 403
If recipient does not exist -> reject HTTP 404
```

### 3.6. Decryption flow

```text
Bob opens Alice
-> GET /messages/offline?peer=alice
-> For each encrypted packet:
   -> validate packet belongs to Bob/Alice
   -> fetch peer public key bundle
   -> derive same ECDH/HKDF message key
   -> AES-GCM decrypt using canonical header as AAD
   -> if tag/header/ciphertext changed, decrypt fails
```

## 4. Demonstration Architecture

Demo có hai lớp: browser demo và backend smoke demo.

### 4.1. Browser demo architecture

```text
User action in UI
-> apps/web/src/app.js
-> fetch REST API or open WebSocket
-> FastAPI route in apps/server/main.py
-> data/demo_store.json
-> UI renders status/lab result
```

Browser demo dùng key thật do Web Crypto sinh ra. Đây là demo chính để trình bày E2EE.

### 4.2. Security Lab architecture

| Lab button | Endpoint | Ý nghĩa kết quả |
|---|---|---|
| Server DB | `GET /lab/messages` | Server-store view chỉ có ciphertext, nonce, tag, metadata |
| Stolen JWT | `GET /lab/messages` từ UI | Có token thì đọc được ciphertext, nhưng không decrypt nếu thiếu private key |
| Replay | `POST /lab/replay` | Chuẩn bị packet cũ, UI/lab expected `REPLAY_REJECTED` |
| Tamper | `POST /lab/tamper` | Server flip ciphertext, browser AES-GCM decrypt fail |
| Key change | `POST /lab/key-substitution` | UI hiển thị fingerprint/key-change warning |
| PCS rekey | `POST /lab/state-compromise` | Trả metric compromise/rekey/recovery point |

### 4.3. Backend smoke architecture

Backend smoke command dùng PowerShell để gọi API trực tiếp. Nó kiểm tra contract server:

- Register/login tạo JWT.
- `/devices` nhận public key.
- `/messages` lưu encrypted packet.
- `/lab/messages` không expose plaintext.
- `/lab/state-compromise` trả metric PCS.

Lưu ý: backend smoke dùng public key giả để test API contract. Browser demo mới là nơi chạy Web Crypto JWK thật và encrypt/decrypt thật.

## 5. Demo Commands

### 5.1. Cài dependency và chạy server

Chạy từ root repository:

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

### 5.2. Reset demo data

Nếu muốn demo lại từ đầu, dừng server rồi chạy:

```powershell
Remove-Item .\data\demo_store.json -Force -ErrorAction SilentlyContinue
```

Sau đó start lại server.

### 5.3. Health check

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Kết quả mong đợi:

```text
ok = true
service = secure-web-chat
password_hasher = argon2id
```

### 5.4. Browser demo flow

Thực hiện trong browser:

1. Register `alice` với password `pass1234`.
2. Logout.
3. Register `bob` với password `pass1234`.
4. Logout.
5. Login `alice`.
6. Open contact `bob`.
7. Gửi message.
8. Chạy Security Lab -> Server DB.
9. Logout Alice.
10. Login `bob`.
11. Open contact `alice`.
12. Refresh messages.
13. Bob đọc plaintext trong browser.
14. Chạy Replay, Tamper, Key change, PCS rekey.

Kết quả cần chụp màn hình:

- Alice/Bob login/register.
- Fingerprint/contact state.
- Alice gửi encrypted message.
- Bob decrypt được message.
- Server DB không có plaintext.
- Replay rejected.
- Tamper detected.
- Key changed warning.
- PCS rekey metric.

### 5.5. Backend test command

```powershell
.\.venv\Scripts\python.exe -m pytest apps/server/tests
```

Kết quả hiện tại cần đạt:

```text
2 passed
```

Nếu có warning từ Starlette/TestClient nhưng test vẫn pass, đó là warning dependency, không phải lỗi logic của project.

### 5.6. API smoke commands

Các lệnh này giả định server đang chạy ở `127.0.0.1:8000`.

```powershell
$base = "http://127.0.0.1:8000"

$alice = Invoke-RestMethod "$base/auth/register" `
  -Method Post `
  -ContentType "application/json" `
  -Body (@{ username = "alice"; password = "pass1234" } | ConvertTo-Json)

$bob = Invoke-RestMethod "$base/auth/register" `
  -Method Post `
  -ContentType "application/json" `
  -Body (@{ username = "bob"; password = "pass1234" } | ConvertTo-Json)

$aliceHeaders = @{ Authorization = "Bearer $($alice.access_token)" }
$bobHeaders = @{ Authorization = "Bearer $($bob.access_token)" }
```

Đăng ký public device key demo:

```powershell
$aliceKey = @{ kty = "EC"; crv = "P-256"; x = "alice_public_x"; y = "alice_public_y"; ext = "true" }
$bobKey = @{ kty = "EC"; crv = "P-256"; x = "bob_public_x"; y = "bob_public_y"; ext = "true" }

Invoke-RestMethod "$base/devices" `
  -Method Post `
  -Headers $aliceHeaders `
  -ContentType "application/json" `
  -Body (@{
    device_id = "alice-browser"
    device_label = "Browser"
    public_key_jwk = $aliceKey
    fingerprint = "alice-fingerprint"
  } | ConvertTo-Json -Depth 10)

Invoke-RestMethod "$base/devices" `
  -Method Post `
  -Headers $bobHeaders `
  -ContentType "application/json" `
  -Body (@{
    device_id = "bob-browser"
    device_label = "Browser"
    public_key_jwk = $bobKey
    fingerprint = "bob-fingerprint"
  } | ConvertTo-Json -Depth 10)
```

Kiểm tra Alice lấy public key bundle của Bob:

```powershell
Invoke-RestMethod "$base/keys/bundle/bob" -Headers $aliceHeaders
```

Kết quả mong đợi:

```text
user_id = bob
device_id = bob-browser
fingerprint = bob-fingerprint
```

Gửi encrypted packet demo:

```powershell
$packet = @{
  version = 1
  algorithm = "ECDH-P-256+HKDF-SHA256+AES-GCM"
  header = @{
    version = 1
    conversation_id = "alice__bob"
    sender_user_id = "alice"
    sender_device_id = "alice-browser"
    recipient_user_id = "bob"
    recipient_device_id = "bob-browser"
    message_number = 1
    ratchet_public_key = "alice-fingerprint"
  }
  nonce = "nonce"
  ciphertext = "ciphertext"
  tag = "tag"
}

$message = Invoke-RestMethod "$base/messages" `
  -Method Post `
  -Headers $aliceHeaders `
  -ContentType "application/json" `
  -Body (@{ packet = $packet } | ConvertTo-Json -Depth 10)
```

Kiểm tra Server DB lab:

```powershell
Invoke-RestMethod "$base/lab/messages" -Headers $bobHeaders
```

Kết quả mong đợi:

```text
plaintext = null
plaintext_exposed = false
ciphertext = ciphertext
```

Kiểm tra replay/tamper/key substitution/PCS:

```powershell
$messageId = $message.message.id

Invoke-RestMethod "$base/lab/replay" `
  -Method Post `
  -Headers $bobHeaders `
  -ContentType "application/json" `
  -Body (@{ message_id = $messageId } | ConvertTo-Json)

Invoke-RestMethod "$base/lab/tamper" `
  -Method Post `
  -Headers $bobHeaders `
  -ContentType "application/json" `
  -Body (@{ message_id = $messageId } | ConvertTo-Json)

Invoke-RestMethod "$base/lab/key-substitution" `
  -Method Post `
  -Headers $aliceHeaders `
  -ContentType "application/json" `
  -Body (@{ username = "bob" } | ConvertTo-Json)

Invoke-RestMethod "$base/lab/state-compromise" `
  -Method Post `
  -Headers $aliceHeaders `
  -ContentType "application/json" `
  -Body (@{
    compromise_at_message = 3
    rekey_at_message = 5
    total_messages = 8
  } | ConvertTo-Json)
```

Kết quả mong đợi:

```text
Replay: expected_result = REPLAY_REJECTED
Tamper: expected_result = TAMPER_REJECTED
Key substitution: expected_result = KEY_SUBSTITUTION_WARNING
PCS: recovered_after_dh_ratchet = true, recovery_point = 5
```

## 6. Demo Results Summary

| Demo | Command/UI action | Expected result | Ý nghĩa |
|---|---|---|---|
| Health | `GET /health` | `ok: true` | Server chạy được |
| Auth | Register/login Alice/Bob | Có access token | User được auth bằng JWT |
| Device key | `POST /devices` | Server lưu public key, không có `d` | Private key không lên server |
| Ciphertext relay | `POST /messages` | Server lưu packet encrypted | Server không cần plaintext để relay |
| Server DB lab | `GET /lab/messages` | `plaintext_exposed: false` | Server compromise không lộ plaintext |
| Plaintext guard | Pytest hoặc API packet có plaintext | HTTP 400 | Backend chặn gửi plaintext |
| Replay | Security Lab -> Replay | `REPLAY_REJECTED` | Packet cũ không nên được xử lý lại |
| Tamper | Security Lab -> Tamper | AES-GCM decrypt fail | Sửa ciphertext/header bị phát hiện |
| Key change | Security Lab -> Key change | Warning | Public key substitution không bị ẩn |
| PCS rekey | Security Lab -> PCS rekey | `recovered_after_dh_ratchet: true` | Minh họa recovery point sau rekey |

## 7. Presentation Script

Khi thuyết trình, nói theo thứ tự này:

1. Risk: server compromise, stolen JWT, tamper, replay, key substitution.
2. Goal: server không đọc plaintext, JWT không decrypt message, client phát hiện tamper/replay/key change.
3. Solution: FastAPI chỉ auth/relay, browser giữ private key và chạy Web Crypto.
4. Architecture: server lưu public key và ciphertext, browser encrypt/decrypt.
5. Demo: Alice gửi message, Bob decrypt, Server DB chỉ thấy ciphertext.
6. Lab: chạy Replay, Tamper, Key change, PCS rekey.
7. Limitation: đây là course prototype, chưa phải full Signal, chưa production-ready, browser compromise vẫn là rủi ro lớn.

Thông điệp kết luận:

```text
JWT answers who can call the server.
E2EE answers who can read the message.
The server can relay ciphertext without seeing plaintext.
Security Lab turns each security claim into visible evidence.
```
