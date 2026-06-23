# Project Gaps and Limitations

File này ghi rõ project hiện tại còn thiếu gì so với một hệ thống chat bảo mật production. Mục đích là trình bày trung thực: project đã có phần demo cốt lõi, nhưng nhiều phần vẫn chỉ ở mức prototype/course MVP.

## 1. Tóm tắt ngắn

Project hiện tại đã làm được:

- Login/register bằng FastAPI.
- Password hash bằng Argon2id khi dependency đầy đủ.
- JWT access token và refresh-token cookie.
- Tạo ECDH key trong browser.
- Lưu private key ở IndexedDB.
- Gửi public key lên server.
- Encrypt/decrypt tin nhắn bằng Web Crypto.
- Server chỉ lưu ciphertext, nonce, tag và metadata.
- Admin dashboard xem password hash, refresh-token hash, public key, ciphertext và event log.
- User thường chỉ chat và xem key/fingerprint.
- Có script `scripts/decrypt_message.mjs` để kiểm tra/decrypt tay một ciphertext khi có đúng private key browser.

Project hiện tại chưa phải production vì:

- Dữ liệu server vẫn lưu trong JSON file, chưa có database thật.
- UI vẫn ở mức demo.
- Crypto protocol chưa phải full Signal/Double Ratchet.
- Chưa có backup/recovery key.
- Chưa có hardening chống XSS, malware, extension độc hại.
- Chưa có deploy production, HTTPS config, monitoring, audit log đầy đủ.

## 2. Storage and Database Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| Server storage | Lưu vào `data/demo_store.json` | Chưa có DB thật, không có migration, index, transaction | Dùng PostgreSQL hoặc SQLite cho demo nâng cao |
| User table | Có `users` trong JSON | Chưa có schema chuẩn, unique constraint DB-level | Tạo bảng `users` với unique username/wallet address |
| Session table | Có `refresh_sessions` trong JSON | Chưa có cleanup job, rotate token đầy đủ | Tạo bảng `refresh_sessions`, thêm revoke/rotate/expiry cleanup |
| Device table | Có `devices` trong JSON | Chưa hỗ trợ nhiều device đúng nghĩa | Tạo bảng `devices`, quản lý active/revoked devices |
| Message table | Có list `messages` trong JSON | Chưa tối ưu query theo conversation, chưa phân trang | Tạo bảng `messages`, index sender/recipient/conversation |
| Event log | Có `security_events` trong JSON | Chưa có audit retention, severity, actor IP/user-agent | Tạo bảng `security_events` và chính sách retention |
| Backup dữ liệu | Chưa có | JSON file dễ mất/hỏng | DB backup/export script |

Điểm cần nói khi thuyết trình:

```text
Hiện tại JSON store giúp demo rõ dữ liệu server đang lưu, nhưng production cần database thật.
```

## 3. UI and UX Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| Login/register | Form đơn giản | Chưa có validation UI đẹp, forgot password, error state chi tiết | Cải thiện form và thông báo lỗi |
| User chat UI | Chat 1-1, contact list, fingerprint view | Chưa có UI production, search, unread count, typing, delivery/read receipt | Làm chat layout đầy đủ hơn |
| Admin dashboard | Bảng hash/ciphertext/public key/events | Chưa có filter, search, pagination, export | Thêm filter theo user/conversation/time |
| Key warning UI | Có fingerprint/key state | Chưa có flow verify safety number chuyên nghiệp | Thêm màn verify key/fingerprint rõ hơn |
| Mobile responsive | Có CSS responsive cơ bản | Chưa test kỹ nhiều viewport | Test mobile/tablet và chỉnh UX |
| Accessibility | Chưa tập trung | Chưa có keyboard nav/ARIA đầy đủ | Audit accessibility |
| Loading/error state | Có trạng thái rất cơ bản | Chưa có skeleton/loading tốt, retry UX | Thêm component trạng thái rõ ràng |

Điểm cần nói:

```text
UI hiện đủ cho demo crypto flow, chưa phải giao diện sản phẩm hoàn chỉnh.
```

## 4. Cryptography and Protocol Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| Device key | ECDH P-256 browser key | Chưa có identity key + signed prekey + one-time prekey | Thiết kế X3DH hoặc protocol tương đương |
| Key exchange | ECDH trực tiếp qua public key directory | Chưa chống server key substitution hoàn chỉnh | Key transparency hoặc signed key bundle |
| Message key | HKDF per-message key | Chưa phải full Double Ratchet | Implement Double Ratchet đầy đủ |
| Replay handling | Packet ID/message number demo | Chưa có replay window production | Lưu receive counters/skipped keys |
| Tamper detection | AES-GCM AAD header | Tốt cho demo, cần test rộng hơn | Test sửa header/ciphertext/tag đầy đủ |
| PCS | Có lab metric/concept | Chưa có DH ratchet message flow thật | Thêm ratchet step và rekey thực tế |
| Group chat | Chưa có | Không hỗ trợ group E2EE | Nghiên cứu MLS hoặc group session |
| File/media encryption | Chưa có | Không gửi file | Thêm encrypt file chunk/key wrapping |

Điểm cần nói:

```text
Project mượn ý tưởng Signal nhưng chưa phải Signal implementation.
```

## 5. Browser Key and Recovery Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| Private key storage | IndexedDB | Nếu browser data mất thì mất key | Thêm backup/recovery phrase |
| Recovery phrase | Chưa có | User chưa restore được key trên máy mới | Sinh 12/24 words hoặc backup code bằng CSPRNG |
| Key export | Chưa có | Chưa export encrypted private key | Export private key đã được wrap/encrypt |
| Key import | Chưa có | Chưa import key khi đổi máy | Import từ recovery phrase hoặc backup file |
| Manual decrypt export | Có thể export tạm để chạy `scripts/decrypt_message.mjs` | Đây là debug/evidence, không phải backup an toàn | Thêm encrypted export/import flow |
| Endpoint compromise | Chưa xử lý | Malware/XSS vẫn có thể lấy key trong browser | CSP, sanitization, security audit, không claim chống máy bị chiếm |
| MetaMask/wallet identity | Chưa có | Chưa connect wallet, chưa ký binding key | Dùng MetaMask để ký identity/key binding, không export private key ví |

Điểm cần nói:

```text
Recovery phrase giúp chống mất key khi đổi máy, không chống được attacker đã chiếm máy.
```

## 6. Authentication and Authorization Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| Password auth | Username/password + hash | Chưa có password reset, email verification, rate limit | Thêm reset flow và rate limiting |
| JWT | HMAC-SHA256 tự implement trong demo | Production nên dùng thư viện JWT chuẩn | Dùng PyJWT/authlib và key rotation |
| Refresh token | HttpOnly cookie + hash | Chưa rotate refresh token theo chuẩn chặt | Rotate refresh token mỗi lần refresh |
| Admin role | Username trong `ADMIN_USERNAMES` | Chưa có role table/permission model | RBAC với roles/permissions trong DB |
| Brute force defense | Chưa có | Login brute force chưa bị giới hạn | Rate limit theo IP/user |
| MFA | Chưa có | Không có 2FA | TOTP/WebAuthn |
| Wallet login | Chưa có | Chưa Sign-In with Ethereum | Nonce + MetaMask signature + JWT |

Điểm cần nói:

```text
Auth hiện đủ cho demo local, chưa đủ chống brute force hoặc vận hành public Internet.
```

## 7. Admin Dashboard Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| View users | Có username/password hash | Chưa filter/search | Search theo username/role |
| View ciphertext | Có nonce/ciphertext/tag | Chưa filter conversation/time | Filter theo user, conversation, date |
| View devices | Có public key/fingerprint | Chưa revoke device từ UI | Nút revoke device |
| View sessions | Có refresh token hash | Chưa revoke session từ UI | Nút revoke session |
| View events | Có event table | Chưa severity, pagination, export | Event severity + export CSV |
| Admin security | Có `require_admin` | Chưa có audit mạnh cho admin action | Audit IP, user-agent, action detail |

Điểm cần nói:

```text
Admin dashboard hiện là bảng quan sát demo server store, chưa phải admin console hoàn chỉnh.
```

## 8. Realtime and Messaging Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| WebSocket notify | Có `/ws` auth bằng JWT | Chưa có reconnect/backoff tốt | Reconnect strategy |
| Polling fallback | 2.5 giây refresh active chat | Tốn request nếu mở rộng user | Server push ổn định hơn |
| Delivery status | Chưa có | Không biết delivered/read | Thêm delivery/read receipt |
| Offline queue | Có `/messages/offline` cơ bản | Chưa có pagination, ack, cleanup | Message cursor + ack |
| Conversation model | Dựa vào sender/recipient/conversation_id trong packet | Chưa có bảng conversations | Tạo conversation table |
| Multi-device | Chưa đúng nghĩa | Một user nhiều device chưa được encrypt fan-out | Encrypt cho từng device key |

## 9. Testing Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| Backend tests | Có pytest cho flow chính | Chưa cover hết endpoint/lỗi cạnh | Thêm negative tests |
| Frontend syntax | Có `node --check` | Chưa có browser automation test | Playwright tests |
| Crypto tests | Có test gián tiếp qua demo | Chưa có vector test độc lập | Test vectors cho HKDF/AES-GCM packet |
| Manual decrypt script | Có `scripts/decrypt_message.mjs` | Chưa có fixture/test tự động cho nhiều packet | Thêm test vector cố định cho script |
| Security tests | Có plaintext rejection/admin 403 | Chưa fuzz packet, tamper header | Fuzz packet validation |
| Performance tests | Chưa có | Chưa đo latency/throughput | Benchmark login/encrypt/decrypt/relay |
| Cross-browser tests | Chưa có | Chưa test Chrome/Edge/Firefox/Mobile | Browser matrix |

Điểm cần nói:

```text
Test hiện kiểm tra boundary quan trọng, nhưng chưa phải security test suite đầy đủ.
```

## 10. Deployment and Operations Gaps

| Phần | Hiện tại đã có | Còn thiếu | Hướng nâng cấp |
|---|---|---|---|
| Local run | Có script Windows setup/run/test | Chưa deploy server thật | Docker hoặc VM/cloud deploy |
| HTTPS | Local HTTP | Production cần HTTPS bắt buộc | Reverse proxy/Nginx/Caddy + TLS |
| Secrets | `JWT_SECRET` env var | Chưa có secret manager/rotation | Secret manager và rotate key |
| Logging | Event log trong JSON | Chưa có structured logs/monitoring | App logs + metrics |
| Error handling | Cơ bản | Chưa có centralized error handling | Error middleware |
| CI/CD | Chưa có | Chưa tự chạy test khi push | GitHub Actions |
| Data migration | Chưa có | Không có migration DB | Alembic/Prisma migration tùy stack |

## 11. Privacy and Security Hardening Gaps

| Phần | Hiện tại | Còn thiếu |
|---|---|---|
| XSS protection | Chưa tập trung | CSP, input sanitization, dependency audit |
| CSRF | Cookie refresh có SameSite Lax | Cần review kỹ nếu mở rộng endpoint cookie |
| Rate limit | Chưa có | Login/API rate limiting |
| Content Security Policy | Chưa có | CSP header |
| Secure cookie | `secure=False` cho local demo | Production phải `secure=True` qua HTTPS |
| Token storage | Access token trong sessionStorage | Cần đánh giá XSS risk kỹ hơn |
| Admin data exposure | Admin xem hash/ciphertext | Cần audit/log và phân quyền chi tiết |
| Device revocation | Chưa đầy đủ | Revoke lost/compromised device |

## 12. Scope Not Implemented Yet

Những thứ chưa làm:

- Database production.
- React/Vue/Next frontend.
- Tailwind/component design system.
- Full Signal protocol.
- X3DH handshake.
- Signed prekeys.
- One-time prekeys.
- Full Double Ratchet.
- Group chat.
- File/image encrypted upload.
- Push notification.
- Mobile app.
- Wallet login bằng MetaMask.
- Recovery phrase/import/export key.
- Multi-device fan-out encryption.
- Production deployment.
- CI/CD.
- Real benchmark dashboard.

## 13. Suggested Next Milestones

Nếu tiếp tục phát triển, nên đi theo thứ tự này:

1. Thay JSON store bằng SQLite hoặc PostgreSQL.
2. Thêm migration/schema rõ ràng cho users, sessions, devices, conversations, messages, events.
3. Thêm recovery phrase hoặc encrypted key backup.
4. Thêm browser automation test cho login/chat/admin.
5. Thêm filter/search/pagination cho admin dashboard.
6. Thêm device revoke và session revoke.
7. Thêm rate limit cho auth endpoints.
8. Thêm CSP và security headers.
9. Thêm wallet login hoặc MetaMask identity binding nếu muốn mở rộng hướng Web3.
10. Nghiên cứu X3DH/Double Ratchet đầy đủ nếu mục tiêu là crypto protocol nghiêm túc hơn.

## 14. One-Slide Summary

```text
Current project = runnable cryptography course prototype.

Already done:
- JWT auth
- browser-side E2EE demo
- ciphertext-only server storage
- admin dashboard for server-side hashes/ciphertext
- user chat + key/fingerprint view

Still missing:
- real database
- production UI/UX
- full Signal/Double Ratchet
- key recovery
- encrypted key export/import
- hardening against XSS/endpoint compromise
- deployment, CI/CD, monitoring
```
