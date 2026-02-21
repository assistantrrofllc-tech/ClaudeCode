# CrewOS — Session Context

**Modular Field Operations Platform for Small Business**
**Tech Quest LLC | Robert Cordero | Feb 2026**

---

## What Is This Repo

This repo contains **CrewLedger** (Module 1 of CrewOS) — an SMS-based receipt and expense tracking system for trades companies. Employees text photos of receipts to a Twilio phone number. The system uses GPT-4o-mini Vision to extract data, confirms with the employee, saves everything, and reports to management and accounting.

**Current state:** Phase 1 complete and deployed. Phase 2A (Proof Ledger) is the current priority.

---

## Key Documents — Read These First

| Document | What It Contains |
|---|---|
| **CREWOS_ROADMAP.md** | Full system roadmap — all 6 modules, build timeline, business model, technical foundation, build guardrails. **This is the living document. Every build decision references it.** |
| **openspec/specs/crewledger-baseline.md** | Foundation spec — complete technical documentation of everything built in Phase 1 (database schema, SMS pipeline, API endpoints, deployment config). |
| **openspec/changes/** | Active feature proposals in progress. Check here before starting new work. |

---

## Build Guardrails

- **Specs before code.** Use OpenSpec (`openspec new change <name>` then `/opsx:ff`). No code without a reviewed plan.
- **Finish one feature before starting the next.** Deploy and verify before moving on.
- **The employee database is sacred.** Every module depends on it. Changes require review.
- **Mobile first on every UI decision.** Field crews live on their phones.
- **Frontend is plain HTML/CSS/JS.** No React, no build step.
- **Real world use is the only proof.** If Kim and the field crew aren't using it, it's not done.

---

## Current Priority: Phase 2A — Proof Ledger

Build in this order:

1. Receipt images — clickable, modal view
2. Employee whitelist — unknown numbers silenced and flagged
3. Employee management page — add/edit/deactivate from dashboard
4. Ledger page — banking style, time filters
5. QuickBooks export wired to current ledger filters

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 / Flask 3.0+ |
| Database | SQLite (WAL mode) |
| SMS | Twilio |
| OCR | GPT-4o-mini Vision API |
| Frontend | Plain HTML/CSS/JS |
| Hosting | Hostinger KVM 2 VPS — srv1306217.hstgr.cloud |
| Deployment | GitHub -> deploy/update.sh |
| Spec management | OpenSpec |

---

## Quick Reference

| What | Where |
|---|---|
| App entry point | `src/app.py` — `create_app()` |
| SMS webhook | `POST /webhook/sms` — `src/api/twilio_webhook.py` |
| SMS routing | `src/messaging/sms_handler.py` |
| OCR processing | `src/services/ocr.py` |
| Database schema | `src/database/schema.sql` |
| Weekly report | `src/services/report_generator.py` + `email_sender.py` |
| Dashboard | `dashboard/templates/` + `dashboard/static/` |
| Deploy scripts | `deploy/setup.sh`, `deploy/update.sh` |
| Tests | `tests/` — run with `pytest` |
| Config | `config/settings.py` — reads from `.env` |

---

## People

| Name | Role | Uses |
|---|---|---|
| Robert | PM / Builder | Full platform |
| Kim | Accountant | Ledger, reports, QuickBooks export |
| Doug | Owner | Dashboard, profitability |
| 10-15 Field Employees | Cardholders | SMS receipt submission |

---

*See CREWOS_ROADMAP.md for the full system roadmap, all 6 modules, and build timeline.*
