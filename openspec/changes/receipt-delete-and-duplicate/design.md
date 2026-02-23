## Context

Receipts currently have 4 statuses: pending, confirmed, flagged, rejected. There is no way to remove a receipt from views without hard deleting it, which is unacceptable for a financial system. Field crews will double-submit receipts and management needs clean tools to handle both scenarios.

## Goals / Non-Goals

**Goals:**
- Soft delete via status change to 'deleted' — fully audited, reversible
- Duplicate marking via status change to 'duplicate' with reference to original
- "Show Hidden" toggle on ledger to reveal deleted/duplicate receipts
- Delete button in receipt modal with confirmation
- All actions logged in receipt_edits audit trail

**Non-Goals:**
- Hard delete of any kind
- Bulk delete
- Automatic duplicate detection (Phase 3)
- Auth/permissions for delete actions

## Decisions

### 1. Status-based soft delete (not a separate is_deleted column)
**Why:** Simpler — one field to filter on. The status CHECK constraint already gates receipt lifecycle. Adding 'deleted' and 'duplicate' as valid statuses keeps the pattern consistent.

### 2. duplicate_of column on receipts table
**Why:** Direct reference to the original receipt ID. Nullable integer FK. Only populated when status = 'duplicate'.

### 3. Reuse existing edit endpoint for status changes
**Why:** The `/api/receipts/<id>/edit` endpoint already handles field updates with audit trail. Adding 'status' to allowed_fields means delete/restore/duplicate all flow through the same audited path.

### 4. ALTER TABLE for schema migration
**Why:** SQLite doesn't support modifying CHECK constraints. We'll recreate the constraint by creating a new column approach — actually, SQLite CHECK constraints are not enforced on ALTER. The simplest path: the CHECK constraint in schema.sql is only used on CREATE TABLE IF NOT EXISTS (which won't run on existing tables). We update schema.sql for new installs and just add the duplicate_of column via ALTER TABLE on the VPS.

## Risks / Trade-offs

- **[CHECK constraint not updated on existing DB]** → SQLite doesn't enforce CHECK on existing rows. The app code handles status validation. Update schema.sql for new installs.
- **[Show Hidden toggle adds complexity]** → Simple boolean toggle, not a new page. Hidden receipts only visible when explicitly requested.
