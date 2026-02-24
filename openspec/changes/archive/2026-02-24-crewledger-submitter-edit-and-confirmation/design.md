## Context

CrewLedger's SMS receipt flow currently sets conversation state to `awaiting_confirmation` after OCR, expecting a YES/NO reply before the receipt is finalized. With A2P 10DLC pending, outbound SMS is blocked — employees never receive the confirmation prompt, leaving receipts in limbo. Additionally, the submitter (employee_id) on a receipt is permanently locked to the SMS sender, and there is no permission gating on receipt editing.

## Goals / Non-Goals

**Goals:**
- Make the receipt employee/submitter editable in the dashboard edit form
- Auto-confirm incoming receipts (skip SMS confirmation step)
- Gate receipt editing behind `crewledger` module `edit` permission
- Maintain audit trail for submitter changes

**Non-Goals:**
- Full auth/login system (permissions default to allow when no session)
- Re-enabling SMS confirmation (that's a future task when A2P clears)
- Changing the receipt status state machine

## Decisions

### 1. Auto-confirm by setting status to `confirmed` directly after OCR
Instead of creating the receipt as `pending` and setting conversation state to `awaiting_confirmation`, set receipt status to `pending` (for admin review) and conversation state to `idle`. Skip the confirmation message entirely. The receipt is accepted immediately and appears in the dashboard for Kim to review.

**Alternative considered:** Set status to `confirmed` directly. Rejected because `pending` means "awaiting Kim's review" which is still the desired workflow — the change is removing the employee confirmation step, not the admin review step.

### 2. Employee dropdown in edit receipt form
Add a `<select>` of active employees to the existing edit receipt form. The `employee_id` field is added to the allowed edit fields in the API. Changes to employee_id are logged in receipt_edits with old and new employee names.

### 3. Permission checks use existing check_permission helper
The `check_permission(None, "crewledger", "edit")` call is added to mutating receipt endpoints. View endpoints remain open. The permission check reads from the session when available, defaults to allow when no auth exists.

### 4. Hide edit/confirm/flag controls for view-only users
Rather than server-side enforcement on every button (which would require auth), pass a `can_edit` flag to the template. JS uses this flag to show/hide mutation controls. Server endpoints still check permissions as defense-in-depth.

## Risks / Trade-offs

- **No real enforcement yet** — Without auth, permission checks default to True. This is intentional scaffolding for when auth is added.
- **Auto-confirm removes employee verification** — Receipts may have OCR errors that employees would have caught. Mitigation: Kim reviews all receipts in the dashboard anyway.
- **Submitter change is powerful** — Could be misused. Mitigation: Full audit trail in receipt_edits table.
