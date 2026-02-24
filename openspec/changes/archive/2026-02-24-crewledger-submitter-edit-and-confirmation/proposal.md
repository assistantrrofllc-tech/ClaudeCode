## Why

Three operational issues are blocking CrewLedger from smooth daily use: (1) receipts are permanently locked to the SMS sender — if Robert submits a receipt that belongs to Mario, Kim cannot reassign it; (2) A2P 10DLC registration is pending so outbound SMS confirmations are blocked, causing the old confirm-before-next-receipt flow to lock out users; (3) any dashboard user can edit receipts regardless of role, with no access control enforcing who should be reviewing vs. just viewing.

## What Changes

- **Editable submitter on receipts:** The Edit Receipt form gains an employee dropdown so admin/edit users can reassign a receipt to any active employee. Change is logged in receipt_edits audit trail.
- **Auto-confirm incoming receipts:** Remove SMS confirmation blocking. Incoming receipts go directly to `pending` status (awaiting admin review). No outbound confirmation SMS sent. Each submission is independent — one user's unconfirmed receipt never blocks another user.
- **Permission-gated receipt editing:** Only users with `edit` or higher access on the `crewledger` module can modify receipts (edit, delete, flag, change status, confirm). View-only users see data but cannot change anything. Confirm/flag controls hidden for view-only users.

## Capabilities

### New Capabilities
- `receipt-submitter-edit`: Ability to change the employee assigned to a receipt after submission, with audit trail.
- `receipt-auto-confirm`: Auto-confirm incoming receipts without SMS round-trip, removing blocking confirmation logic.
- `receipt-permission-gating`: Permission-based access control for receipt editing operations using the crewledger module permission.

### Modified Capabilities

## Impact

- `src/api/dashboard.py` — Edit receipt form, receipt API endpoints, confirm/flag actions
- `src/messaging/sms_handler.py` — SMS receipt flow, confirmation logic
- `dashboard/templates/` — Edit receipt modal, ledger row actions
- `src/services/permissions.py` — Already exists, will be consumed by dashboard routes
