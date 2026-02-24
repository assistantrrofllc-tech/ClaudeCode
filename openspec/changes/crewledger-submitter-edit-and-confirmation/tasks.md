## 1. Auto-Confirm Receipts

- [ ] 1.1 In `sms_handler.py`, change `_handle_receipt_submission()` to set conversation state to `idle` instead of `awaiting_confirmation` after creating receipt
- [ ] 1.2 Return a simple acknowledgment message instead of the confirmation prompt (e.g., "Got it, {name}! Receipt for ${total} at {vendor} has been logged.")
- [ ] 1.3 Verify that `awaiting_confirmation` state routing still works (keep the handler for backwards compat with any receipts already in that state)

## 2. Editable Submitter

- [ ] 2.1 Add `employee_id` to the allowed editable fields in `POST /api/receipts/<id>/edit`
- [ ] 2.2 Log employee_id changes in receipt_edits with human-readable employee names (old and new)
- [ ] 2.3 Add employee dropdown to the edit receipt form in the frontend (app.js `toggleEditForm`)
- [ ] 2.4 Pre-select the current submitter in the dropdown

## 3. Permission Gating

- [ ] 3.1 Add `check_permission` calls to receipt mutation endpoints (edit, confirm, flag, delete)
- [ ] 3.2 Pass `can_edit` flag to ledger template based on permission check
- [ ] 3.3 Conditionally render edit/confirm/flag/delete controls in frontend based on `can_edit`

## 4. Testing

- [ ] 4.1 Test auto-confirm flow (receipt created, conversation state = idle)
- [ ] 4.2 Test submitter edit via API with audit trail
- [ ] 4.3 Run full test suite — verify no regressions
