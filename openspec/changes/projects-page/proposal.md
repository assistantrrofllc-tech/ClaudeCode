## Why

Projects are currently managed inside the Settings page as a secondary section. As the platform grows toward CrewGroup (multi-module), projects deserve their own dedicated page with full CRUD, inline editing, and proper nav placement. The data and API endpoints already exist — this is a frontend restructure.

## What Changes

- New `/projects` page accessible from main nav (between Employees and Settings gear icon)
- Table displays: name, project code, address, city/state, status, start date, receipt count, total spend
- Add Project form: name, code, address, city, state, start date, end date, notes
- Inline edit per row (click to edit fields)
- Deactivate (set status to completed) per row instead of hard delete
- Remove the projects section from Settings page — replace with a link card to `/projects`
- Nav bar updated with "Projects" link

## Capabilities

### New Capabilities
- `projects-page`: Dedicated project management page with full CRUD, inline editing, and nav integration

### Modified Capabilities
- `crewledger-baseline`: Settings page no longer contains projects section; nav bar gains Projects link

## Impact

- **New file:** `dashboard/templates/projects.html`
- **Modified:** `dashboard/templates/base.html` (nav link), `dashboard/templates/settings.html` (remove projects section, add link card), `src/api/dashboard.py` (new `/projects` route)
- **No API changes** — existing `/api/projects` CRUD endpoints are reused
- **No database changes** — schema already has all needed columns
