# GitHub Publish Checklist

Use this checklist before pushing the repository so another machine can clone and run the project.

## Files That Must Be Present

| File or folder | Purpose |
|---|---|
| `README.md` | First-run instructions and project overview |
| `requirements.txt` | Python dependencies |
| `.env.example` | Example environment variables |
| `.gitignore` | Prevents local data, logs, secrets, and virtualenv files from being committed |
| `apps/server/main.py` | FastAPI backend |
| `apps/server/db.py` | SQLAlchemy models and database engine (SQLite / PostgreSQL) |
| `alembic.ini` and `migrations/` | Alembic configuration and schema migrations |
| `apps/web/index.html` and `apps/web/src/` | Browser UI and Web Crypto logic |
| `apps/server/tests/test_app.py`, `apps/server/tests/test_db.py` | Backend API and database (FK/cascade/conversation) tests |
| `scripts/setup_windows.ps1` | Creates venv and installs dependencies |
| `scripts/run_dev.ps1` | Starts the local server |
| `scripts/test.ps1` | Runs backend tests |
| `scripts/reset_demo_data.ps1` | Removes local demo data (SQLite DB and legacy JSON) |
| `scripts/migrate_json_to_db.py` | One-time import of a legacy JSON store into the database |
| `scripts/decrypt_message.mjs` | Manually decrypts one stored message with an exported browser device key for evidence/debugging |

## Do Not Push

Check that these files are not staged:

```text
.venv/
data/secure_chat.db
data/secure_chat.db-wal
data/secure_chat.db-shm
data/demo_store.json
server*.log
*.err.log
.env
tmp/
private/
*.jwk
*.key
*.pem
```

Quick check:

```powershell
git status --short
```

Optional secret scan:

```powershell
rg -n -i "(secret|token|password|private[_-]?key|BEGIN PRIVATE|DATABASE_URL|`"d`"\s*:)" .
```

False positives in docs are expected. Real secret values should not be committed.

## Fresh Clone Test

On another Windows machine:

```powershell
git clone <repo-url>
cd secure-web-chat-jwt-hybrid-ratchet-pcs
.\scripts\setup_windows.ps1
.\scripts\test.ps1
.\scripts\run_dev.ps1
```

If PowerShell blocks scripts:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_dev.ps1
```

Open:

```text
http://127.0.0.1:8000
```

Expected result:

- `.\scripts\test.ps1` reports the backend test suite passing. The current suite has 9 tests (API boundaries + database integrity).
- `/health` returns `ok: true`.
- Browser can register `alice` and `bob`.
- Alice can send an encrypted message to Bob.
- User UI shows chat plus key/fingerprint information.
- Login as `admin` opens the admin dashboard.
- Admin dashboard shows hashes/public keys/ciphertext, not plaintext/private keys.

Optional manual decrypt evidence:

```powershell
node scripts\decrypt_message.mjs --list
node scripts\decrypt_message.mjs --device .\tmp\<exported-device>.json --index 0
```

Keep the exported device JSON in `tmp/` or another ignored path.

## Reset Before Demo

If demo data is messy:

```powershell
.\scripts\reset_demo_data.ps1
.\scripts\run_dev.ps1
```

The server recreates the local SQLite database (`data/secure_chat.db`) automatically on next start.
