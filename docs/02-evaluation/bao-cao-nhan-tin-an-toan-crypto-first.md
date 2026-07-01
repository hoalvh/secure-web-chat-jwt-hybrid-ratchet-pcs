# Báo cáo mô tả hệ thống nhắn tin an toàn theo hướng crypto-first

Ngày cập nhật: 01/07/2026

## 1. Tóm tắt mục tiêu

Dự án xây dựng một ứng dụng nhắn tin web một-một, tập trung vào bảo mật nội dung tin nhắn. Mục tiêu chính không phải là làm một mạng xã hội hoàn chỉnh, mà là chứng minh được các nguyên tắc mật mã ứng dụng trong một hệ thống nhắn tin:

- Máy chủ xác thực người dùng và chuyển tiếp dữ liệu, nhưng không được biết nội dung tin nhắn.
- Khóa riêng, khóa phiên và trạng thái phiên được giữ ở trình duyệt người dùng.
- Tin nhắn được mã hóa đầu-cuối trước khi gửi lên server.
- Server chỉ lưu ciphertext khi cần, ví dụ người nhận đang offline hoặc người gửi chọn lưu.
- Mỗi phiên trò chuyện có session key động, lấy cảm hứng từ cách các ứng dụng lớn dùng identity key, signed pre-key, one-time pre-key và key derivation.

Cách trình bày đúng với thầy: đây là một prototype môn Mật mã ứng dụng theo hướng Signal/Messenger-inspired. Không nên nói đây là full Signal, vì hệ thống hiện chưa có full Double Ratchet, skipped-message keys, key transparency và multi-device fanout chuẩn sản phẩm lớn.

## 2. Các app nhắn tin lớn làm gì?

### Signal / Messenger / WhatsApp

Các hệ thống nhắn tin E2EE hiện đại thường tách server khỏi bí mật nội dung. Server giữ vai trò định tuyến, lưu khóa công khai và hỗ trợ offline delivery. Phần mã hóa nằm ở client.

Theo Signal X3DH specification, mỗi người dùng có identity key dài hạn, signed pre-key và tập one-time pre-key để người gửi có thể bắt đầu phiên ngay cả khi người nhận offline. Messenger E2EE whitepaper của Meta cũng mô tả mô hình tương tự: server trả về identity key, signed pre-key và one-time pre-key; one-time pre-key chỉ dùng một lần và bị xóa khỏi server sau khi được yêu cầu. Sau đó client tạo ephemeral key và tính master secret bằng nhiều phép ECDH.

Trong Messenger whitepaper, công thức session setup cho một cuộc trò chuyện một-một có dạng:

```text
ECDH(identity_initiator, signed_prekey_recipient)
|| ECDH(ephemeral_initiator, identity_recipient)
|| ECDH(ephemeral_initiator, signed_prekey_recipient)
|| ECDH(ephemeral_initiator, one_time_prekey_recipient)
```

Nếu không còn one-time pre-key thì bỏ nhánh cuối. Từ secret này, client dùng HKDF để tạo root key và chain key.

WhatsApp cũng công bố hướng multi-device: mỗi thiết bị companion kết nối độc lập nhưng vẫn giữ E2EE. Vấn đề khó ở sản phẩm lớn là mỗi user có nhiều thiết bị, nên tin nhắn phải được mã hóa/fanout cho từng device session.

Điểm đáng chú ý khác là key transparency. WhatsApp và Messenger đều có hướng kiểm chứng khóa để giảm rủi ro server tráo khóa công khai. Đây là lớp rất quan trọng nếu muốn đi gần sản phẩm thật.

### Zalo

Tài liệu trợ giúp chính thức của Zalo cho biết Zalo có cơ chế sao lưu/khôi phục, tin nhắn văn bản có thể được sao lưu lên máy chủ của Zalo, và tin nhắn trong trò chuyện mã hóa đầu cuối vẫn được sao lưu mặc định trừ khi người dùng tắt sao lưu trò chuyện mã hóa đầu cuối.

Do Zalo không công bố whitepaper protocol chi tiết như Signal hoặc Meta, báo cáo này không khẳng định Zalo dùng X3DH/Double Ratchet. Khi so sánh với Zalo nên nói thận trọng: Zalo có các cơ chế riêng về lưu trữ, sao lưu, khôi phục và E2EE, nhưng không có tài liệu kỹ thuật công khai đủ để đối chiếu từng bước như Messenger/Signal.

### WeChat

WeChat không phải là hình mẫu E2EE để học theo. Citizen Lab phân tích rằng cơ chế của WeChat là mã hóa giữa client và server, không phải mã hóa đầu-cuối; server WeChat có thể giải mã và đọc tin nhắn. Vì vậy WeChat nên được đưa vào phần đối chiếu như một ví dụ transport encryption, không phải E2EE đúng nghĩa.

## 3. Kiến trúc của dự án

Hệ thống gồm hai lớp chính:

```text
Browser client
  - Sinh và giữ private keys
  - Kiểm tra chữ ký khóa
  - Tạo session key động
  - Mã hóa/giải mã AES-GCM
  - Lưu session state và lịch sử local trong IndexedDB

FastAPI server
  - Đăng ký, đăng nhập, JWT
  - Lưu password hash và refresh-token hash
  - Lưu public device key, signing public key, signed pre-key, one-time pre-key
  - Relay ciphertext qua WebSocket nếu người nhận online
  - Lưu ciphertext offline queue khi cần
```

Điểm quan trọng: server không giữ plaintext, private key, session root key hay message key.

## 4. Thành phần khóa

### 4.1 Identity signing key

Mỗi người dùng có một ECDSA/P-256 identity signing key. Khóa public được upload lên server để người khác kiểm tra chữ ký. Khóa private được mã hóa bằng AES-GCM với khóa dẫn xuất từ mật khẩu rồi lưu trong IndexedDB.

Vai trò:

- Ký device key.
- Ký signed pre-key.
- Ký one-time pre-key.
- Giúp người nhận phát hiện public key bị thay đổi bất thường.

Code liên quan:

- `apps/web/src/app.js`: `ensureIdentityKey`, `encryptIdentityKey`, `tryDecryptIdentityKey`
- `apps/server/main.py`: `/keys/signing-key`

### 4.2 Device identity key

Trình duyệt tạo một cặp ECDH/P-256 device key. Public key được gửi lên server, private key ở lại IndexedDB.

Vai trò:

- Tham gia ECDH trong session setup.
- Đại diện cho thiết bị hiện tại của user.
- Được identity signing key ký để giảm rủi ro server tự tạo device key giả.

Code liên quan:

- `apps/web/src/app.js`: `ensureDevice`
- `apps/server/main.py`: `/devices`

### 4.3 Signed pre-key và one-time pre-key

Client tạo:

- Một signed pre-key, dùng để người gửi bắt đầu phiên khi người nhận offline.
- Nhiều one-time pre-key, mỗi khóa chỉ dùng một lần để tăng forward secrecy cho session đầu.

Server chỉ nhận public pre-key. Private pre-key nằm trong IndexedDB.

Điểm đã sửa để giống app lớn hơn:

- Mở contact chỉ gọi `GET /keys/bundle/{username}`, không tiêu hao OTP.
- Khi thật sự bắt đầu session mới, client gọi `GET /keys/bundle/{username}?reserve_otp=true`.
- Server trả về một OTP nếu còn và đánh dấu consumed ngay trong cùng transaction.
- Điều này tránh lỗi race: hai người gửi cùng lấy một OTP.

Code liên quan:

- `apps/web/src/app.js`: `generatePreKeys`, `getKeyBundle`, `createOutboundSession`
- `apps/server/main.py`: `key_bundle`

## 5. Luồng mã hóa khi gửi tin

Khi Alice gửi tin cho Bob:

```text
1. Alice mở Bob
2. Browser tải public bundle của Bob
3. Browser kiểm tra device signature, signed pre-key signature, OTP signature nếu có
4. Nếu chưa có outbound session:
   - Gọi /keys/bundle/bob?reserve_otp=true
   - Sinh ephemeral ECDH key mới
   - Tính X3DH-style root key
   - Tạo session_id
   - Lưu root key và counter trong IndexedDB
5. Từ session root key, HKDF tạo message key theo message_number
6. AES-GCM mã hóa plaintext
7. Header được đưa vào AAD để chống sửa metadata quan trọng
8. Gửi packet lên server cùng store_mode
```

Công thức DH hiện tại:

```text
DH1 = sender device identity private x recipient signed pre-key public
DH2 = sender ephemeral private x recipient device identity public
DH3 = sender ephemeral private x recipient signed pre-key public
DH4 = sender ephemeral private x recipient one-time pre-key public, nếu có OTP được reserve

root_key = HKDF(DH1 || DH2 || DH3 || DH4)
```

Sau đó:

```text
session chain key = HKDF(root_key, session_id + sender + recipient)
message key       = HKDF(chain key, message_number)
ciphertext        = AES-GCM(message key, nonce, plaintext, AAD=canonical(header))
```

Code liên quan:

- `apps/web/src/app.js`: `computeX3dhRootKey`
- `apps/web/src/app.js`: `deriveSessionMessageKey`
- `apps/web/src/app.js`: `encryptPacket`

## 6. Luồng giải mã khi nhận tin

Khi Bob nhận packet đầu tiên từ Alice:

```text
1. Bob thấy header có session_id và ephemeral_public_key
2. Bob lấy bundle công khai của Alice để biết identity/device public key
3. Bob lấy private signed pre-key và private OTP trong IndexedDB
4. Bob tính lại cùng DH1, DH2, DH3, DH4 theo phía nhận
5. Bob tạo root key giống Alice
6. Bob thử AES-GCM decrypt với AAD là canonical(header)
7. Chỉ khi decrypt/authenticate thành công, Bob mới lưu inbound session
8. Nếu OTP đã dùng, Bob xóa private OTP khỏi IndexedDB
```

Điểm bảo mật quan trọng: session inbound không được lưu trước khi xác thực AES-GCM thành công. Nếu packet bị sửa, tag sai hoặc header sai, client không lưu trạng thái giả.

Code liên quan:

- `apps/web/src/app.js`: `decryptPacket`

## 7. Server giảm tối đa tác động vào cuộc trò chuyện

Trước khi sửa, server thiên về lưu message hơn. Hiện tại server có ba chế độ lưu:

| Chế độ | Ý nghĩa |
|---|---|
| `auto` | Nếu recipient online thì relay-only, không ghi DB; nếu offline thì lưu ciphertext offline queue |
| `never` | Không cho server lưu; nếu recipient offline thì trả lỗi |
| `always` | Lưu ciphertext vì user muốn lưu/offline demo |

UI có mục `Server storage` để chọn chế độ.

Server chỉ thấy:

- sender id
- recipient id
- conversation id
- message number
- session id
- nonce
- ciphertext
- tag
- timestamp/routing metadata

Server không thấy:

- plaintext
- private key
- session root key
- message key
- password rõ
- refresh token rõ

Code liên quan:

- `apps/server/main.py`: `relay_or_store_packet`
- `apps/server/main.py`: `validate_encrypted_packet`
- `apps/web/index.html`: `storeModeSelect`
- `apps/web/src/app.js`: gửi `store_mode` trong `sendMessage`

## 8. Các kiểm tra bảo mật backend

Backend hiện có các rào chắn:

- Reject packet có chữ `plaintext` trong JSON canonical.
- Reject nested private JWK material như `d`, `private_key_jwk`, `private_key`.
- Header phải đủ `version`, `conversation_id`, `sender_user_id`, `recipient_user_id`, `message_number`.
- Token user phải khớp sender trong packet.
- `conversation_id` phải khớp hai participant.
- `message_number` phải là số dương.
- Chống duplicate message number theo session/conversation scope.
- Không lưu message nếu recipient không tồn tại.
- Admin dashboard chỉ cho admin.

Code liên quan:

- `apps/server/main.py`: `contains_private_jwk_material`
- `apps/server/main.py`: `validate_encrypted_packet`
- `apps/server/tests/test_app.py`

## 9. So sánh với app lớn

| Tiêu chí | Messenger/Signal/WhatsApp | Dự án hiện tại |
|---|---|---|
| E2EE client-side | Có | Có, mã hóa bằng Web Crypto trong browser |
| Identity key | Có | Có ECDSA identity signing key |
| Signed pre-key | Có | Có |
| One-time pre-key | Có, chỉ dùng một lần | Có, reserve/consume atomically khi lập session |
| Ephemeral key | Có | Có cho session setup |
| HKDF/root/chain key | Có | Có session root và session chain |
| Double Ratchet đầy đủ | Có trong Signal-style systems | Chưa có đầy đủ |
| Skipped-message keys | Có trong hệ production | Chưa có |
| Multi-device fanout | Có | Chưa có, hiện chủ yếu một browser device |
| Key transparency | Messenger/WhatsApp có hướng triển khai | Chưa có |
| Encrypted backup/history sync | Messenger có Labyrinth/Minos-style encrypted storage | Chưa có encrypted backup server-side |
| Server plaintext access | Không nên có trong E2EE | Server không nhận plaintext trong luồng chính |

Kết luận so sánh: dự án đã đi đúng hướng crypto-first giống phần nền của Messenger/Signal, nhưng phạm vi là prototype môn học. Điểm mạnh là đã chứng minh được public pre-key bundle, OTP one-time, session key động, AES-GCM AAD, relay-only khi online và ciphertext-only offline queue.

## 10. Giới hạn cần nói thật

Các điểm chưa nên khẳng định quá mức:

1. Chưa phải full Signal Protocol.
2. Chưa có full Double Ratchet với DH ratchet liên tục.
3. Chưa có skipped-message key cho tin nhắn out-of-order.
4. Chưa có key transparency hoặc QR/safety number verification hoàn chỉnh.
5. Chưa có multi-device fanout như WhatsApp/Messenger.
6. Chưa có encrypted backup/history sync kiểu Messenger Labyrinth.
7. Browser IndexedDB không chống được XSS, malware hoặc extension độc hại.
8. Demo dùng P-256 Web Crypto vì browser hỗ trợ sẵn, không phải Curve25519 như Signal.
9. Private keys còn extractable để phục vụ demo/kiểm tra môn học.

Cách nói an toàn trước thầy:

> Em không nói sản phẩm này là Signal hoàn chỉnh. Em mô phỏng các thành phần cốt lõi của nhắn tin E2EE: identity key, signed pre-key, one-time pre-key, X3DH-style session setup, HKDF session/message keys, AES-GCM AAD và server relay/lưu ciphertext-only. Những phần sản phẩm lớn còn có mà em chưa làm là full Double Ratchet, skipped-message keys, key transparency, multi-device fanout và encrypted backup.

## 11. Kịch bản demo nên trình bày

### Demo 1: Server không đọc được tin nhắn

1. Đăng ký Alice và Bob.
2. Alice mở Bob.
3. Alice gửi tin.
4. Mở admin dashboard hoặc database.
5. Chỉ thấy ciphertext, nonce, tag, header metadata.
6. Không thấy plaintext.

Ý nghĩa: chứng minh JWT/server auth không phải cơ chế mã hóa nội dung; nội dung được mã hóa ở browser.

### Demo 2: Offline queue chỉ lưu ciphertext

1. Bob logout/offline.
2. Alice gửi tin ở mode `auto`.
3. Server lưu ciphertext vì Bob offline.
4. Bob login lại và mở Alice.
5. Bob decrypt local thành plaintext.

Ý nghĩa: server chỉ làm hàng đợi offline, không giải mã.

### Demo 3: Relay-only khi online

1. Bob online qua WebSocket.
2. Alice gửi tin ở mode `auto`.
3. Server relay qua WebSocket, không ghi message vào DB.

Ý nghĩa: giảm tối đa tác động của server vào cuộc trò chuyện.

### Demo 4: Không cho lưu server

1. Chọn `Server storage = never`.
2. Nếu Bob offline, Alice gửi sẽ bị từ chối.

Ý nghĩa: người dùng có quyền chọn không dùng offline queue server.

### Demo 5: OTP one-time

1. Gọi bundle thường: không trả OTP.
2. Gọi bundle với `reserve_otp=true`: trả một OTP.
3. Gọi reserve lần nữa: OTP cũ không còn.

Ý nghĩa: one-time pre-key không bị dùng lại.

## 12. Kết quả kiểm thử đã chạy

Các lệnh đã chạy:

```powershell
.\scripts\test.ps1
node --check apps\web\src\app.js
```

Kết quả:

```text
17 passed, 1 warning
JavaScript syntax check OK
```

Smoke test thủ công/API:

- `/health` trả OK.
- API reserve OTP: preview không có OTP, reserve lần đầu có OTP, reserve lần hai không còn OTP.
- Browser smoke: Alice gửi offline, Bob đăng nhập lại mở chat và thấy tin nhắn `decrypted locally`.

## 13. Câu hỏi thầy có thể bắt bẻ và câu trả lời

### Hỏi: Server có đọc được tin nhắn không?

Không. Server chỉ nhận header, nonce, ciphertext và tag. Plaintext được mã hóa bằng AES-GCM ở browser trước khi gửi. Backend còn có kiểm tra reject nếu packet chứa trường plaintext.

### Hỏi: JWT có phải mã hóa tin nhắn không?

Không. JWT chỉ chứng minh user nào được gọi API server. Mã hóa tin nhắn do Web Crypto ở browser thực hiện bằng session/message key.

### Hỏi: Vì sao cần signed pre-key và one-time pre-key?

Signed pre-key giúp người gửi bắt đầu phiên khi người nhận offline. One-time pre-key tăng forward secrecy cho lần thiết lập phiên đầu và chỉ dùng một lần. Đây là ý tưởng quan trọng trong X3DH/Signal-style messaging.

### Hỏi: Server có thể tráo public key không?

Hiện tại client kiểm tra chữ ký device key và pre-key bằng identity signing key, đồng thời lưu TOFU fingerprint để phát hiện identity đổi. Tuy nhiên hệ thống chưa có key transparency hoặc QR/safety-number verification hoàn chỉnh, nên chưa chống triệt để malicious server ở lần gặp đầu.

### Hỏi: Có phải full Signal không?

Không. Hệ thống là Signal-inspired prototype. Có identity key, signed pre-key, one-time pre-key và session key động, nhưng chưa có full Double Ratchet, skipped-message keys, multi-device fanout và key transparency production-grade.

### Hỏi: Nếu mất IndexedDB thì sao?

Mất private key/session state cục bộ. Tin đã lưu server dưới dạng ciphertext có thể không giải mã được nếu mất khóa. Đây là lý do app lớn cần encrypted backup/recovery mechanism.

### Hỏi: Vì sao server vẫn lưu ciphertext khi offline?

Vì offline delivery cần hàng đợi. Nhưng server chỉ lưu ciphertext, không lưu plaintext/key. Nếu user không muốn server lưu, chọn mode `never`.

## 14. Tài liệu tham khảo

- Signal, X3DH Key Agreement Protocol: https://signal.org/docs/specifications/x3dh/
- Signal, Double Ratchet Algorithm: https://signal.org/docs/specifications/doubleratchet/
- Signal, Sesame session management: https://signal.org/docs/specifications/sesame/
- Meta, Messenger End-to-End Encryption Overview: https://engineering.fb.com/wp-content/uploads/2023/12/MessengerEnd-to-EndEncryptionOverview_12-6-2023.pdf
- Meta, Labyrinth Encrypted Message Storage Protocol: https://engineering.fb.com/wp-content/uploads/2023/12/TheLabyrinthEncryptedMessageStorageProtocol_12-6-2023.pdf
- Meta, WhatsApp multi-device capability: https://engineering.fb.com/2021/07/14/security/whatsapp-multi-device/
- Meta, WhatsApp key transparency: https://engineering.fb.com/2023/04/13/security/whatsapp-key-transparency/
- Zalo Help, dữ liệu được Zalo sao lưu: https://help.zalo.me/huong-dan/chuyen-muc/quan-ly-tai-khoan-zalo/sao-luu-va-khoi-phuc/chi-tiet-ve-cac-du-lieu-duoc-zalo-sao-luu/
- Citizen Lab, WeChat MMTLS FAQ: https://citizenlab.ca/research/should-we-chat-too-security-analysis-of-wechats-mmtls-encryption-protocol/should-we-chat-too-faq/
