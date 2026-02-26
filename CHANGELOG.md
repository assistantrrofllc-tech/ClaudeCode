# Changelog

All notable changes to CrewOS / CrewLedger.

## [2026-02-26] CrewAsset — Vehicles Module

### Added
- **Fleet overview page** with summary stats (total vehicles, total spend, avg cost), vehicle cards, search/filter
- **Vehicle detail page** with maintenance history, vendor summary, mileage tracking
- **Maintenance CRUD** — add/edit/delete maintenance records with role-based permissions
- 6 new API routes under `/fleet/` (overview, detail, maintenance list, add, edit, delete)
- **CrewAsset module tab** enabled in navigation with orange/amber color theme
- Sub-navigation for CrewAsset modules (Vehicles active, Inventory/Equipment placeholders)
- 12 new tests for fleet routes and permissions (`tests/test_fleet.py`)

### New Files
- `src/api/fleet.py` — Fleet blueprint with 6 routes
- `dashboard/templates/fleet.html` — Fleet overview template
- `dashboard/templates/fleet_detail.html` — Vehicle detail template
- `tests/test_fleet.py` — Fleet integration tests

### Permissions
- Add/edit maintenance: `require_permission("crewasset", "edit")` — company_admin+ only
- Delete maintenance: `require_role("super_admin", "company_admin")` — admin-tier only
- View routes: any authenticated user

## [2026-02-26] — Role-Based Permissions + Legal Pages

### Added
- **4-tier role-based permissions** — super_admin, company_admin, manager, employee with route-level access control
- **User management page** — `/admin/users` (super_admin only) for CRUD on authorized_users
- **Legal page routes** — `/legal/privacy-policy`, `/legal/terms-and-conditions`, `/legal` (public, no auth)
- **Data isolation** — employee role sees only own receipts, own crew record, masked contacts
- **Contact masking** — `mask_phone()` and `mask_email()` helpers for restricted roles
- 53 new tests (22 permission unit tests + 31 role access integration tests)

### Changed
- `src/services/permissions.py` — Full rewrite: `ROLE_HIERARCHY`, `DEFAULT_ACCESS`, `require_role()` decorator, `require_permission()` decorator
- `src/api/auth.py` — Session stores `system_role` + `employee_id` with legacy fallbacks
- `src/app.py` — Context processor injects role-based template vars; module tab filtering; legal routes
- `src/api/dashboard.py` — `@require_role` on 30+ routes; data isolation for employee role
- `src/api/admin_tools.py` — `@require_role("super_admin", "company_admin")` on all routes
- Templates (`ledger.html`, `crew.html`, `crew_detail.html`, `home.html`) — UI elements hidden by role
- Legal HTML files — internal links updated to use route paths

### Schema
- New columns on `authorized_users`: `system_role`, `employee_id`
- 8 users assigned roles (2 super_admin, 3 company_admin, 3 manager)

### New Files
- `src/api/user_management.py` — User management blueprint
- `dashboard/templates/user_management.html` — User management UI
- `tests/test_permissions.py` — Permission unit tests
- `tests/test_role_access.py` — Role access integration tests

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
