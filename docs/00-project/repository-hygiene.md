# Repository Hygiene

This document defines what should and should not be committed to the repository.

## Repository Visibility

The project repository should be private during development because it contains unfinished course work, experiment plans, and implementation details. However, a private repository is not a safe place for secrets.

Do not commit real secrets even if the repository is private.

## Repository Name

Recommended GitHub repository name:

```text
secure-web-chat-jwt-hybrid-ratchet-pcs
```

Reason:

- It is readable.
- It matches the project title.
- It avoids spaces and special characters.
- It is easier to clone, reference, and use in commands than the full formal title.

The README title can keep the full project name:

```text
Secure Web Chat with JWT Authentication, Hybrid Ratchet and Post-Compromise Security
```

## Safe to Commit

These files are safe and useful to commit:

- `README.md`
- `docs/**`
- `apps/**` source code and tests
- `.env.example`
- `requirements.txt`
- `scripts/**`
- `.gitignore`

`scripts/decrypt_message.mjs` is safe to commit because it contains only the decrypt algorithm and CLI logic. The device JSON passed to it is not safe to commit.

## Do Not Commit

Never commit:

- `.env`
- `.env.local`
- Real database URLs with production credentials.
- Real `JWT_SECRET` values.
- Raw access tokens or refresh tokens.
- Private device keys.
- IndexedDB exports containing private JWK field `d`.
- Device JSON files used with `scripts/decrypt_message.mjs`.
- Ratchet state dumps.
- Real user data.
- The local database from runs: `data/secure_chat.db` (and `-wal` / `-shm`) and any legacy `data/demo_store.json`.
- `tmp/` exports, screenshots with secrets, or copied browser storage dumps.
- `server*.log` or `*.err.log`.
- `.venv/` or other virtual environments.
- Generated `node_modules/`.
- Build output such as `dist/` or `build/`.
- Browser test artifacts such as `playwright-report/`.
- Local IDE folders such as `.vscode/` or `.idea/`.

## About `.env.example`

`.env.example` is safe to commit because it contains example development values only. It should show which environment variables are available, but it must not contain real secrets.

Current local demo variables include:

```text
JWT_SECRET
JWT_ISSUER
JWT_AUDIENCE
JWT_ACCESS_TOKEN_TTL_SECONDS
REFRESH_COOKIE_NAME
REFRESH_TOKEN_TTL_SECONDS
SECURE_CHAT_DATA_DIR
DATABASE_URL
COOKIE_SECURE
CORS_ORIGINS
```

`DATABASE_URL` is empty for local SQLite; for deployment it holds the managed
Postgres connection string and must be kept out of git. `COOKIE_SECURE=true` and
`CORS_ORIGINS` are production (HTTPS) switches.

Developers may create a local `.env` or set variables directly in PowerShell. Local `.env` files must stay ignored.

## Before First Push

Recommended checklist:

- Confirm `.gitignore` exists.
- Confirm `.env` does not appear in `git status`.
- Confirm no private keys are present.
- Confirm no local database (`data/secure_chat.db*`), JSON store, or logs are staged.
- Confirm no `tmp/*.json` device exports or IndexedDB private-key dumps are staged.
- Confirm README links work.
- Commit documentation and scaffold first.

Useful check before committing:

```text
git status --short
```

Optional secret scan:

```text
rg -n -i "(secret|password|token|private[_-]?key|BEGIN PRIVATE|DATABASE_URL|\\\"d\\\"\\s*:)" .
```

False positives are expected in documentation, but real secret values should be removed.
