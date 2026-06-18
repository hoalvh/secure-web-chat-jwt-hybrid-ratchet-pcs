# Documentation Index

This folder is organized as a small documentation set rather than a flat list of notes.

## 00. Project

General project information and stack-level decisions.

| Document | Purpose |
|---|---|
| [Team and Execution Plan](00-project/team-and-execution-plan.md) | Team members, roles, ownership matrix, milestones, and branch workflow |
| [Detailed Vietnamese Project Description](00-project/project-description-vn.md) | Full Vietnamese explanation for teammates, including architecture, flows, APIs, crypto design, demo script, and limitations |
| [Project Scope and Non-Goals](00-project/project-scope.md) | Defines MVP depth, non-goals, database scope, and algorithm scope |
| [Technology Decisions](00-project/technology-decisions.md) | Architecture, stack choices, alternatives, and trade-offs |
| [Repository Hygiene](00-project/repository-hygiene.md) | GitHub repository naming, commit safety, `.env` rules, and secret-handling notes |

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
| [Results Template](02-evaluation/results-template.md) | Tables and interpretation rules for security and performance results |

## Proposal

The `proposal/` folder is reserved for proposal-specific drafts, exported text, and submission material.

## Naming Convention

- `00-project/` contains general project metadata and high-level decisions.
- `01-design/` contains technical design documents.
- `02-evaluation/` contains experiments, benchmark plans, and result templates.
- File names are descriptive and stable enough to reference from the report and presentation.
