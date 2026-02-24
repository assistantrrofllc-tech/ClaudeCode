## Why

Clicking an employee in the crew list needs to show their full record — identity card, cert details with expiry dates, and document links. This is where managers go to verify an employee's cert status before sending them to a job site.

## What Changes

- New route `/crew/<employee_id>` renders employee detail page
- Top section: identity card (name, phone, email, crew, role, status, photo placeholder, edit button)
- Cert badge row (same color-coded badges as list view, clickable to jump to cert in table)
- Certifications table: Cert Type | Issued | Expires | Status | Document | Actions (edit/delete)
- "Add Certification" button and form (modal or inline)
- API endpoints: GET single employee with full cert details, POST/PUT/DELETE certification records
- Bottom placeholders: safety violations log (empty state), notes field
- Mobile-first layout

## Capabilities

### New Capabilities
- `crewcert-employee-detail`: Full employee profile page with cert management

### Modified Capabilities

## Impact

- **Routes:** New `/crew/<employee_id>` page route, new cert CRUD API endpoints
- **Templates:** New `crew_detail.html`
- **CSS:** Identity card styles, cert table styles
- **JS:** Cert CRUD operations, badge-to-table scroll links
