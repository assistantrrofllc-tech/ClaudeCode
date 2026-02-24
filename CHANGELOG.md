# Changelog

All notable changes to CrewOS / CrewLedger.

## [2026-02-24] — CrewCert Module + Infrastructure

9 changes shipped in one session.

### Added
- **Dashboard tab navigation** — Module tabs (Ledger, Crew) with separate routes, sticky tab bar, CSS custom properties
- **CrewCert employee list** — `/crew` route with roster, cert badge summaries, search/filter, add employee form
- **CrewCert employee detail** — `/crew/<id>` with identity card, cert CRUD, notes section, inline edit
- **Cert image viewer** — Modal document viewer with download, path traversal protection
- **PDF splitter tool** — `/admin/cert-splitter` for splitting multi-page cert PDFs and assigning to employees
- **Bulk CSV import** — `/admin/cert-import` with fuzzy name matching via thefuzz
- **CrewComms DB scaffold** — `communications` table for SMS/email/call records, SMS backup import script
- **Permissions framework** — `user_permissions` table, `check_permission()` helper, `system_role` on employees
- **Editable submitter** — Employee dropdown on receipt edit form with audit trail
- **Auto-confirm receipts** — Skip SMS confirmation (A2P 10DLC pending), receipts go straight to pending
- **Permission-gated editing** — Receipt mutation endpoints require `edit` access on crewledger module

### Schema
- New tables: `certification_types` (9 seeded), `certifications`, `communications`, `user_permissions`
- New columns on `employees`: `email`, `notes`, `system_role`

### Dependencies
- Added: pdfplumber, pypdf, thefuzz

## [2026-02-23] — Category Management Rebuild

### Changed
- Rebuilt category system: 8 categories, receipt-level assignment, Settings UI
- Auto-categorize line items
- Category column on ledger

## [2026-02-22] — Baseline

### Added
- Phase 1 complete: SMS receipt pipeline, OCR, dashboard, exports, weekly reports
- Baseline spec v2.1 archived
