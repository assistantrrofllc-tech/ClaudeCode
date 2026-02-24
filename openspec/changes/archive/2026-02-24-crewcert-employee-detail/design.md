## Context

Change 2 built the employee list with cert badge summary. Now we need the detail page that opens when clicking an employee row. The certifications table and API already exist from Change 2. We need CRUD endpoints for individual certs and the detail page UI.

## Goals / Non-Goals

**Goals:**
- Employee identity card with all contact info and edit capability
- Full certifications table with status, dates, document link column
- CRUD for individual certification records
- Badge row that scrolls to the cert in the table
- Mobile-friendly detail page

**Non-Goals:**
- Cert document upload (Change 4)
- PDF splitting (Change 5)
- Bulk import (Change 6)
- Profile photo upload (placeholder only for now)

## Decisions

### 1. Single page with anchor links for badge-to-table scroll

Clicking a badge in the header scrolls to the matching cert row in the table via `#cert-<slug>`. Simple, no complex JS needed.

### 2. Inline edit form for employee fields

Edit button toggles editable fields inline (same pattern as receipt edit). No separate edit page.

### 3. Add Certification uses a modal form

Modal over the page with fields: cert type (dropdown), issued date, expiry date, issuing org, notes. Document upload comes in Change 4.

### 4. Soft delete for certs

Delete sets `is_active = 0` rather than removing the row. Preserves history.

## Risks / Trade-offs

- **Profile photo placeholder** — Shows a generic avatar icon. Real upload comes later. No broken image issues.
- **Notes field at bottom** — Simple textarea, saved via API. No rich text.
