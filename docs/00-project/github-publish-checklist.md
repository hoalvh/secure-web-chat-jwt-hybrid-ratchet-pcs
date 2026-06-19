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
| `apps/web/index.html` and `apps/web/src/` | Browser UI and Web Crypto logic |
| `apps/server/tests/test_app.py` | Smoke tests for backend security boundaries |
| `scripts/setup_windows.ps1` | Creates venv and installs dependencies |
| `scripts/run_dev.ps1` | Starts the local server |
| `scripts/test.ps1` | Runs backend tests |
| `scripts/reset_demo_data.ps1` | Removes local demo JSON data |

## Do Not Push

Check that these files are not staged:

```text
.venv/
data/demo_store.json
server*.log
*.err.log
.env
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

- `.\scripts\test.ps1` reports `2 passed`.
- `/health` returns `ok: true`.
- Browser can register `alice` and `bob`.
- Alice can send an encrypted message to Bob.
- Security Lab -> Server DB shows ciphertext only.

## Reset Before Demo

If demo data is messy:

```powershell
.\scripts\reset_demo_data.ps1
.\scripts\run_dev.ps1
```

The server recreates `data/demo_store.json` automatically.
