## Context

The Crew tab exists as an empty placeholder from Change 1. The employees table already has basic fields (name, phone, role, crew, is_active). We need to add email support and a full certification data model, then build the list UI that shows cert status badges per employee.

## Goals / Non-Goals

**Goals:**
- Certification data model that supports any cert type with issue/expiry tracking
- Employee list API that returns cert summary per employee in a single query
- Mobile-first roster UI with color-coded cert badges
- Search/filter by name, crew, or cert status

**Non-Goals:**
- Employee detail view (Change 3)
- Cert document upload/viewing (Change 4)
- Cert data import (Changes 5-6)
- Notifications for expiring certs (future)

## Decisions

### 1. Separate certification_types lookup table

Cert types are stored in a lookup table rather than hardcoded strings. This allows adding/renaming cert types without schema changes. Seeded with the 9 known types.

### 2. Cert status computed from expiry date, not stored

Status (valid/expiring/expired) is computed at query time: `expires_at > now + 90 days` = valid, `expires_at > now` = expiring, else expired. No stored status column to go stale.

### 3. Single API endpoint returns employee + cert summary

`/api/crew/employees` returns each employee with an array of cert badges (type, status, color). One query with LEFT JOINs avoids N+1. Badge array is pre-computed server-side.

### 4. Client-side search/filter

The employee list is small enough (<100 employees typically) to filter client-side with JS. No server-side search endpoint needed.

## Risks / Trade-offs

- **Email column on employees** — Adding a nullable column is non-breaking. Existing employees will have NULL email until manually set. Mitigation: UI shows "—" for missing email.
- **90-day expiring threshold** — Hardcoded for now. Could become a setting later. Acceptable for MVP.
