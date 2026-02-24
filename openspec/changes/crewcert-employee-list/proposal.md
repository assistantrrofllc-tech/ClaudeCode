## Why

The Crew tab (added in Change 1) needs its first real content: an employee roster with certification status at a glance. Field managers need to quickly see who has valid certs, who's expiring, and who's missing required training — all from their phone. This is the foundation of the CrewCert module.

## What Changes

- New `certification_types` table seeded with 9 badge types (OSHA 10, OSHA 30, First Aid/CPR, Fall Protection, Extended Reach Forklift, Driver, Bilingual, Crew Lead, Card Holder)
- New `certifications` table linking employees to cert types with issue/expiry dates and document paths
- Add `email` column to employees table
- API endpoints: employee list with cert summary, certification types list
- Crew tab populated with employee roster — each row shows name, phone, email, crew/role, status, and color-coded cert badge row
- Search/filter bar (name, crew, cert status)
- "Add Employee" button
- Click row navigates to employee detail (wired in Change 3)
- Mobile-first — readable on a phone in the field

## Capabilities

### New Capabilities
- `crewcert-data-model`: Certification types and certifications tables with seed data
- `crewcert-employee-list`: Employee roster with cert badge summary, search/filter, mobile-first layout

### Modified Capabilities

## Impact

- **Database:** New `certification_types` and `certifications` tables, `email` column on employees
- **Routes:** `/crew` route updated with real data, new API endpoints `/api/cert-types` and `/api/crew/employees`
- **Templates:** `crew.html` rebuilt with employee list UI
- **CSS:** Badge icon styles for cert status colors (green/yellow/red/gray)
- **JS:** Search/filter logic, click-to-navigate
