## 1. Database Schema

- [ ] 1.1 Add `email` column to employees table (ALTER TABLE migration)
- [ ] 1.2 Create `certification_types` table with seed data (9 types)
- [ ] 1.3 Create `certifications` table with foreign keys and unique constraint
- [ ] 1.4 Update schema.sql with new tables

## 2. API Endpoints

- [ ] 2.1 Create `/api/cert-types` endpoint (GET — list all cert types)
- [ ] 2.2 Create `/api/crew/employees` endpoint (GET — employee list with cert badge summary)
- [ ] 2.3 Wire Add Employee to work from crew page (reuse existing POST /api/employees)

## 3. Crew Tab UI

- [ ] 3.1 Rebuild `crew.html` with employee roster table/cards
- [ ] 3.2 Add cert badge row per employee (color-coded icons)
- [ ] 3.3 Add search/filter bar (client-side JS filtering by name, crew, cert status)
- [ ] 3.4 Add "Add Employee" button and inline form/modal
- [ ] 3.5 Make employee rows clickable → `/crew/<employee_id>`
- [ ] 3.6 Add click-to-call on phone numbers

## 4. CSS

- [ ] 4.1 Add cert badge styles (`.cert-badge`, color variants for valid/expiring/expired/none)
- [ ] 4.2 Add crew list styles (responsive card/row layout)

## 5. Testing

- [ ] 5.1 Test cert types API returns 9 types
- [ ] 5.2 Test crew employees API returns employee list with cert summary
- [ ] 5.3 Test badge status computation (valid >90d, expiring <90d, expired, none)
- [ ] 5.4 Run full test suite — all existing tests pass
