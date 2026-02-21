# Proposal: CrewLedger Phase 1 Baseline

## What

Document the current state of CrewLedger Phase 1 ("The Ledger") as the foundation spec. This captures everything already built and deployed — the SMS receipt pipeline, OCR processing, confirmation flow, weekly email reports, database schema, and VPS deployment.

## Why

Every future feature, change, and Claude session needs a single source of truth for what the system currently does. This baseline spec replaces handoff documents and ensures no decisions are lost between sessions.

## What Changes

Nothing changes in the code. This is a documentation-only change that creates the foundation spec at `openspec/specs/crewledger-baseline.md`.

## What Is Documented

1. System overview and user roles
2. Complete technology stack with versions
3. Full database schema (7 tables, all columns, indexes)
4. SMS receipt pipeline (webhook → OCR → confirm → save)
5. Employee auto-registration flow
6. Confirmation, manual entry, and missed receipt flows
7. OCR processing details and prompt
8. Weekly email report system
9. All API endpoints
10. Image storage conventions
11. Configuration settings
12. Project directory structure
13. Production deployment architecture
14. What is NOT yet built (future phases)
