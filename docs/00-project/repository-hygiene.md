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
- `apps/**` source code
- `packages/**` source code
- `prisma/schema.prisma`
- `prisma/migrations/**`
- `experiments/**` scripts and small result summaries
- `benchmarks/**` scripts and selected result summaries
- `.env.example`
- `docker-compose.yml`
- `.gitignore`

## Do Not Commit

Never commit:

- `.env`
- `.env.local`
- Real database URLs with production credentials.
- JWT private keys.
- Refresh-token secrets.
- Private device keys.
- Ratchet state dumps.
- Real user data.
- Generated `node_modules/`.
- Build output such as `dist/` or `build/`.
- Browser test artifacts such as `playwright-report/`.
- Local IDE folders such as `.vscode/` or `.idea/`.

## About `.env.example`

`.env.example` is safe to commit because it contains example development values only. It should show which environment variables are required, but it must not contain real secrets.

Current example values such as `secure_chat` are acceptable for local Docker development. They are not production credentials.

When implementation begins, developers should create a local `.env` file copied from `.env.example`:

```text
cp .env.example .env
```

The `.env` file must stay local and is ignored by `.gitignore`.

## Docker Compose Passwords

The password in `docker-compose.yml` is a local development password for the Docker PostgreSQL container. It is acceptable for local demo use, but it should not be reused in production or deployment environments.

If the project later adds deployment instructions, production secrets must be injected through the deployment platform's secret manager or environment-variable system.

## Before First Push

Recommended checklist:

- Confirm `.gitignore` exists.
- Confirm `.env` does not exist in `git status`.
- Confirm no private keys are present.
- Confirm no local IDE settings are staged.
- Confirm README links work.
- Commit documentation and scaffold first.

Useful check before committing:

```text
git status --short
```

Optional secret scan:

```text
rg -n -i "(secret|password|token|private[_-]?key|BEGIN PRIVATE|DATABASE_URL)" .
```

False positives are expected in documentation, but real secret values should be removed.
