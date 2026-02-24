## ADDED Requirements

### Requirement: Auto-confirm incoming receipts
The SMS receipt flow SHALL accept incoming receipts immediately without waiting for employee confirmation via SMS. Receipts SHALL be created with status `pending` and conversation state set to `idle`.

#### Scenario: Receipt submitted via SMS
- **WHEN** an employee sends a receipt photo via SMS
- **THEN** the system SHALL create the receipt with status = 'pending'
- **AND** the conversation state SHALL be set to 'idle' (not 'awaiting_confirmation')
- **AND** no outbound confirmation SMS SHALL be sent

#### Scenario: Independent submissions
- **WHEN** employee A has a pending receipt and employee B submits a new receipt
- **THEN** employee B's receipt SHALL be accepted immediately
- **AND** employee A's pending status SHALL have no effect on employee B

### Requirement: No blocking confirmation logic
The system SHALL NOT block new receipt submissions based on unconfirmed previous receipts. Each receipt submission SHALL be independent.

#### Scenario: Same employee submits multiple receipts
- **WHEN** an employee submits a second receipt while the first is still pending
- **THEN** the second receipt SHALL be accepted and created normally
