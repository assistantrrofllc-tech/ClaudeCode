# OpenSpec Change — Delete Receipt + Duplicate Flag
# Run: openspec new change receipt-delete-and-duplicate
# Then use this as the proposal

---

## Proposal — Soft Delete and Duplicate Marking for Receipts

### What We Are Building
Two related receipt management features:
1. Soft delete — remove a receipt from all views without wiping it from the database
2. Duplicate flag — mark a receipt as a duplicate of another

Both are essential for a financial system. Hard deletes are never acceptable in
an accounting context. Everything must be recoverable and auditable.

---

## Feature 1 — Soft Delete Receipt

### Where It Lives
- Delete button in the receipt modal — bottom row alongside Edit Receipt and Edit History
- Confirmation prompt required before deleting — "Are you sure you want to delete
  this receipt? It can be restored from the Ledger." with Cancel and Delete buttons
- No accidental deletions

### What Happens On Delete
- Receipt status set to 'deleted' — no rows removed from database ever
- Receipt disappears from all default views immediately — dashboard, ledger, exports
- Deletion logged in receipt_edits audit trail:
  - field_changed: 'status'
  - old_value: previous status
  - new_value: 'deleted'
  - edited_at: timestamp
  - edited_by: 'management'

### Viewing and Restoring Deleted Receipts
- Ledger page gets a "Show Deleted" toggle — off by default
- When toggled on, deleted receipts appear with a red "DELETED" status badge
- Each deleted receipt shows a Restore button in the modal
- Restore sets status back to previous status before deletion
- Restore also logged in audit trail

### What Deleted Receipts Do NOT Affect
- They do not count toward any totals
- They do not appear in exports unless Show Deleted is active
- They do not appear in email reports
- They do not count toward project spend

---

## Feature 2 — Duplicate Flag

### Where It Lives
- In the receipt edit form — a "Mark as Duplicate" checkbox or button
- When marked as duplicate, a reference field appears: "Duplicate of Receipt #___"
- Management can enter the receipt ID of the original

### What Happens When Marked Duplicate
- Receipt status set to 'duplicate'
- Receipt hidden from default ledger view
- Duplicate badge shown in red when visible
- Duplicate reference ID stored in receipts table — add duplicate_of column (nullable integer)
- Logged in audit trail same as delete

### Viewing Duplicates
- Same "Show Deleted" toggle also surfaces duplicates — rename to "Show Hidden"
- Or add separate "Show Duplicates" filter — designer's call, keep it clean
- Restore option available same as deleted receipts

### Why This Matters
Field crews will eventually double-submit receipts — same receipt texted twice,
or two employees submitting the same purchase. Management needs a clean way to
mark one as the duplicate without deleting either record permanently.

---

## Database Changes

Modify receipts table:
- Add duplicate_of column — INTEGER nullable, foreign key to receipts.id
- Status field already exists — add 'deleted' and 'duplicate' as valid values
  alongside existing: confirmed, pending, flagged, missed

No new tables required.

---

## UI Changes

Receipt modal — bottom button row:
- Before: Edit Receipt | Edit History
- After: Edit Receipt | Edit History | Delete

Ledger page — filter bar:
- Add "Show Hidden" toggle (off by default)
- When on: shows deleted and duplicate receipts with appropriate badges

---

## Deploy Checklist

1. Run full test suite — all tests must pass
2. Add tests for:
   - Delete receipt — status becomes deleted, disappears from default view
   - Restore receipt — status returns to previous value
   - Confirmation prompt — receipt not deleted without confirmation
   - Duplicate flag — status becomes duplicate, duplicate_of reference saved
   - Show Hidden toggle — deleted and duplicate receipts appear
   - Audit trail — both delete and duplicate actions logged correctly
3. Push to GitHub
4. Merge to main
5. Update CHANGELOG.md — date, features, test count
6. Update README.md if needed
7. Run: bash /opt/crewledger/deploy/update.sh
8. Verify on live dashboard:
   - Delete the Bays Smoke Shop test receipt
   - Confirm it disappears from ledger
   - Toggle Show Hidden — confirm it reappears with DELETED badge
   - Restore it — confirm it returns to normal view
   - Mark Home Depot receipt as duplicate — confirm it hides
9. Confirm with Robert before moving on

---

## What NOT To Build In This Change

- Hard delete of any kind — never
- Bulk delete — not yet
- Admin-only delete permissions — auth comes later
- Automatic duplicate detection — that is a Phase 3 intelligence feature
