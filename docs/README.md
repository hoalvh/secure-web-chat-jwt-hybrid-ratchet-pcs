# Documentation Index

This folder is organized as a small documentation set rather than a flat list of notes.

The current runnable MVP uses Python FastAPI, vanilla JavaScript styled with Tabler/Bootstrap (CDN), Browser Web Crypto, IndexedDB, and a SQLAlchemy database (SQLite locally, PostgreSQL for deployment, schema managed by Alembic). The user UI is chat plus key/fingerprint inspection; admin UI is a server dashboard for hashes, public keys, ciphertext, conversations, and events. A larger React/TypeScript frontend remains future expansion where mentioned.

## 00. Project

General project information and stack-level decisions.

| Document | Purpose |
|---|---|
| [Team and Execution Plan](00-project/team-and-execution-plan.md) | Team members, roles, ownership matrix, milestones, and branch workflow |
| [Project Scope and Non-Goals](00-project/project-scope.md) | Defines MVP depth, non-goals, database scope, and algorithm scope |
| [Technology Decisions](00-project/technology-decisions.md) | Architecture, stack choices, alternatives, and trade-offs |
| [Repository Hygiene](00-project/repository-hygiene.md) | GitHub repository naming, commit safety, `.env` rules, and secret-handling notes |
| [GitHub Publish Checklist](00-project/github-publish-checklist.md) | What to keep, what not to push, and how to verify a fresh clone |

## 01. Design

Security and protocol design documents.

| Document | Purpose |
|---|---|
| [Threat Model](01-design/threat-model.md) | Assets, trust boundaries, attacker scenarios, and expected protections |
| [Authentication and JWT](01-design/authentication-and-jwt.md) | Login, password hashing, JWT, refresh token, and WebSocket auth design |
| [Device Identity and Key Binding](01-design/device-identity-and-key-binding.md) | Browser device keys, public key binding, IndexedDB private key storage, and key-change handling |
| [E2EE Protocol Design](01-design/e2ee-protocol-design.md) | Current P-256/HKDF/AES-GCM encrypted messaging protocol and packet format |
| [Key Schedule and Ratchet](01-design/key-schedule-and-ratchet.md) | Root keys, chain keys, message keys, simplified ratchet, and PCS limits |
| [Security UX](01-design/security-ux.md) | UI states that make encryption, verification, warnings, and recovery visible |

## 02. Evaluation

Experiment and benchmark planning.

| Document | Purpose |
|---|---|
| [Experiment Plan](02-evaluation/experiment-plan.md) | Server compromise, stolen JWT, replay, tamper, key substitution, FS, and PCS experiments |
| [Code Flow and Runtime Explanation](02-evaluation/code-flow-runtime-explanation.md) | Runtime walkthrough: browser storage, token structure, server database, chat flow, admin flow |
| [Risks, Goals, Solution, Architecture, Demo](02-evaluation/risks-goals-solution-architecture-demo.md) | Clear explanation of risks-to-goals mapping, architecture, demo architecture, expected results, and commands |
| [Results Template](02-evaluation/results-template.md) | Tables and interpretation rules for security and performance results |
| [Project Gaps and Limitations](02-evaluation/project-gaps-and-limitations.md) | Current missing pieces: full Signal/Double Ratchet, key recovery, security hardening, deployment/CI |

## Naming Convention

- `00-project/` contains general project metadata and high-level decisions.
- `01-design/` contains technical design documents.
- `02-evaluation/` contains security experiment plans, demo evidence notes, and result templates.
- File names are descriptive and stable enough to reference from the final report or slides.
