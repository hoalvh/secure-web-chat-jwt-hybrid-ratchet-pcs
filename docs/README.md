# Documentation Index

This folder is organized as a small documentation set rather than a flat list of notes.

The current runnable MVP uses Python FastAPI, HTML/CSS/vanilla JavaScript, Browser Web Crypto, IndexedDB, and a local JSON demo store. Larger React/TypeScript/PostgreSQL plans are documented only as future expansion where mentioned.

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
| [Device Identity and Key Binding](01-design/device-identity-and-key-binding.md) | Device keys, signed prekeys, safety numbers, and key-change handling |
| [E2EE Protocol Design](01-design/e2ee-protocol-design.md) | Signal-inspired encrypted messaging protocol and packet format |
| [Key Schedule and Ratchet](01-design/key-schedule-and-ratchet.md) | Root keys, chain keys, message keys, symmetric ratchet, and DH ratchet |
| [Security UX](01-design/security-ux.md) | UI states that make encryption, verification, warnings, and recovery visible |

## 02. Evaluation

Experiment and benchmark planning.

| Document | Purpose |
|---|---|
| [Experiment Plan](02-evaluation/experiment-plan.md) | Server compromise, stolen JWT, replay, tamper, key substitution, FS, and PCS experiments |
| [Risks, Goals, Solution, Architecture, Demo](02-evaluation/risks-goals-solution-architecture-demo.md) | Clear explanation of risks-to-goals mapping, architecture, demo architecture, expected results, and commands |
| [Results Template](02-evaluation/results-template.md) | Tables and interpretation rules for security and performance results |

## Naming Convention

- `00-project/` contains general project metadata and high-level decisions.
- `01-design/` contains technical design documents.
- `02-evaluation/` contains security experiment plans, demo evidence notes, and result templates.
- File names are descriptive and stable enough to reference from the final report or slides.
