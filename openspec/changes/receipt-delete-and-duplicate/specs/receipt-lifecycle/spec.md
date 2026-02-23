## ADDED Requirements

### Requirement: Soft delete receipt
The system SHALL support soft-deleting receipts by setting status to 'deleted'.

#### Scenario: Delete from modal
- **WHEN** user clicks Delete in receipt modal
- **THEN** confirmation dialog appears
- **AND** on confirm, receipt status is set to 'deleted' via edit endpoint
- **AND** change is logged in receipt_edits audit trail
- **AND** receipt disappears from default views

#### Scenario: Deleted receipts excluded from totals
- **WHEN** receipts have status 'deleted'
- **THEN** they are excluded from dashboard stats, ledger totals, exports, and email reports

#### Scenario: Restore deleted receipt
- **WHEN** user views a deleted receipt via Show Hidden toggle
- **AND** clicks Restore in the modal
- **THEN** status returns to 'confirmed'
- **AND** restore is logged in audit trail

### Requirement: Duplicate flag
The system SHALL support marking receipts as duplicates with a reference to the original.

#### Scenario: Mark as duplicate
- **WHEN** user clicks "Mark Duplicate" in receipt modal
- **THEN** a prompt asks for the original receipt ID
- **AND** receipt status is set to 'duplicate'
- **AND** duplicate_of column is set to the original receipt ID
- **AND** change is logged in audit trail

#### Scenario: Duplicate receipts hidden by default
- **WHEN** receipts have status 'duplicate'
- **THEN** they are excluded from default views same as deleted

### Requirement: Show Hidden toggle on ledger
The ledger page SHALL have a "Show Hidden" toggle to reveal deleted and duplicate receipts.

#### Scenario: Toggle shows hidden receipts
- **WHEN** user enables "Show Hidden" on ledger
- **THEN** deleted receipts appear with red "DELETED" badge
- **AND** duplicate receipts appear with red "DUPLICATE" badge
- **AND** each shows Restore button in modal

## MODIFIED Requirements

### Requirement: Receipt status values
#### Scenario: Extended status set
- **GIVEN** the receipts table status field
- **THEN** valid values are: 'pending', 'confirmed', 'flagged', 'rejected', 'deleted', 'duplicate'
