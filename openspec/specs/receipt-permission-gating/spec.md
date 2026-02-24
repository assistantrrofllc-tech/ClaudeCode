# receipt-permission-gating Specification

## Purpose
TBD - created by archiving change crewledger-submitter-edit-and-confirmation. Update Purpose after archive.
## Requirements
### Requirement: Edit permission required for receipt mutations
Only users with `edit` or higher access level on the `crewledger` module SHALL be able to modify receipt records. This includes editing fields, changing status, confirming, flagging, and deleting receipts.

#### Scenario: Edit-level user can modify receipts
- **WHEN** a user with `edit` access on crewledger submits a receipt edit
- **THEN** the edit SHALL be processed normally

#### Scenario: View-only user cannot modify receipts
- **WHEN** a user with only `view` access attempts to edit a receipt
- **THEN** the system SHALL return a 403 Forbidden response

### Requirement: Hidden edit controls for view-only users
The dashboard SHALL hide confirm, flag, edit, and delete controls for users who do not have `edit` access on crewledger. View-only users SHALL see receipt data but not mutation controls.

#### Scenario: View-only user sees read-only dashboard
- **WHEN** a view-only user loads the ledger page
- **THEN** receipt data SHALL be visible
- **AND** edit, confirm, flag, and delete buttons SHALL NOT be rendered

### Requirement: Default to allow when no auth
Until authentication is implemented, all permission checks SHALL default to True (allow), maintaining current permissive behavior.

#### Scenario: No session defaults to full access
- **WHEN** no user session exists
- **THEN** all permission checks SHALL return True
- **AND** all edit controls SHALL be visible

