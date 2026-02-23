# Proposal — Ledger Bug Fixes + Clean Template Repo

Two things in this change:
1. Three bug fixes on the ledger page
2. Copy the entire project into a clean generic template repo

---

## Part 1 — Ledger Bug Fixes

### Bug 1 — Trash Icon Not Working
The trash icon on each ledger row does nothing when clicked.

Fix:
- Wire the trash icon click to trigger the soft delete confirmation prompt
- Confirmation: "Are you sure you want to delete this receipt? It can be
  restored later." with Cancel and Delete buttons
- On confirm: set status to 'deleted', hide from default view, log in audit trail
- Behavior must match the delete flow already built in the receipt modal

### Bug 2 — Delete Button Missing From Receipt Modal
The receipt modal bottom row shows Edit Receipt and Edit History but no Delete button.

Fix:
- Add Delete button to the bottom row of the receipt modal
- Triggers the same soft delete confirmation prompt as the trash icon
- Same audit trail logging

### Bug 3 — Status Badge Is Not Actionable
PENDING status shows as a badge but there is no way to change it from the
ledger row without opening the full modal and editing.

Fix:
- Make the status badge on each ledger row clickable
- Clicking opens a small inline dropdown or popover with these options:
  - Confirm — sets status to 'confirmed', badge turns green
  - Flag — sets status to 'flagged', badge turns red
  - Delete — triggers soft delete confirmation
- Change takes effect immediately without a page reload
- Status change logged in audit trail
- This lets Admin quickly clear a queue of pending receipts from the
  ledger row without opening each one individually

---

## Part 2 — Clean Template Repo

### What To Do
Copy the entire current project into a new GitHub repo called:
`crewledger-template`

### What To Clean In The Template Copy
Do a full find and replace across all code, comments, templates,
configuration files, and documentation:

| Replace | With |
|---|---|
| Any specific person's name | Generic role (Admin, Manager, Field Employee) |
| Any company name | Client Company |
| Any real email addresses | placeholder@clientcompany.com |
| Any real phone numbers | +10000000000 |
| Any real IP addresses or hostnames | your-vps-hostname |
| Any API keys or tokens | YOUR_KEY_HERE |
| R&R specific project names | Sample Project |

### What To Remove From The Template
- All sample data and seed scripts containing real information
- Any hardcoded credentials
- Any client-specific configuration in .env or config files
- GitHub Actions secrets references specific to current VPS

### What To Keep In The Template
- Full codebase — all features built through current state
- OpenSpec folder — baseline spec and all archived changes
- CHANGELOG.md — redacted of client names
- README.md — updated to reflect this is a template
- deploy/ folder — with placeholder values in config
- All tests — with generic test data only

### README.md Update For Template
Add a section at the top:

```
## CrewLedger — Client Template
This is the clean template repo for CrewLedger deployments.
To deploy for a new client:
1. Fork this repo
2. Update .env with client credentials
3. Run deploy/setup.sh on the client VPS
4. Load client employee data via the dashboard bulk import
5. Configure email settings from the settings page
```

### After Template Is Created
- Current repo (ClaudeCode) stays as the R&R Florida live instance
- Template repo is the starting point for every new client
- New client = fork template, configure, deploy

---

## Deploy Checklist

1. Fix trash icon — test soft delete from ledger row works
2. Fix delete button in modal — test confirmation and audit trail
3. Fix status badge — test confirm, flag, delete from ledger row
4. Run full test suite — all tests must pass
5. Add tests for all three bug fixes
6. Push fixes to GitHub
7. Merge to main
8. Update CHANGELOG.md — date, fixes, test count
9. Update README.md if needed
10. Run: bash /opt/crewledger/deploy/update.sh
11. Verify on live site:
    - Trash icon triggers confirmation and deletes
    - Modal has delete button and it works
    - Clicking PENDING badge shows dropdown, confirm turns it green
12. Create crewledger-template repo on GitHub
13. Copy and clean codebase into template repo
14. Verify template has no real names, emails, credentials, or client data
15. Confirm with owner before moving on

---

## What NOT To Build In This Change

- Hard deletes — never
- Bulk status changes — not yet
- Automatic status detection — Phase 3
- Any new features beyond what is listed above
