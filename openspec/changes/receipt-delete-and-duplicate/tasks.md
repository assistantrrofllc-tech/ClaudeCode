## Tasks

### Task 1: Database changes
- Update schema.sql CHECK constraint to include 'deleted' and 'duplicate'
- Add duplicate_of column (INTEGER nullable FK) to receipts table in schema.sql
- Run ALTER TABLE on VPS to add duplicate_of column

### Task 2: Backend — add status to edit endpoint + new delete/duplicate endpoints
- Add 'status' and 'duplicate_of' to allowed_fields in api_edit_receipt
- Add DELETE endpoint: POST /api/receipts/<id>/delete (sets status to deleted)
- Add POST /api/receipts/<id>/restore (sets status back to confirmed)
- Add POST /api/receipts/<id>/duplicate (sets status to duplicate, accepts duplicate_of)
- All changes logged via existing audit trail
- Exclude deleted/duplicate from dashboard stats, summary, exports, reports

### Task 3: Frontend — receipt modal buttons
- Add Delete button to modal footer (red, with confirmation dialog)
- Add "Mark Duplicate" button to modal footer
- Duplicate prompt asks for original receipt ID
- Show Restore button when viewing deleted/duplicate receipts
- Modal shows DELETED or DUPLICATE badge when applicable

### Task 4: Frontend — ledger Show Hidden toggle
- Add "Show Hidden" toggle button to ledger filter bar
- When active, pass include_hidden=1 to /api/receipts
- Deleted receipts show with red DELETED badge
- Duplicate receipts show with red DUPLICATE badge + "of #X" reference

### Task 5: Update filters to exclude hidden by default
- /api/receipts excludes deleted and duplicate by default
- /api/receipts?include_hidden=1 includes them
- /api/dashboard/stats excludes deleted and duplicate
- /api/dashboard/summary excludes deleted and duplicate
- /export/quickbooks excludes deleted and duplicate
