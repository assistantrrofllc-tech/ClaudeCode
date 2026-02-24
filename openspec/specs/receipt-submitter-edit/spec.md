# receipt-submitter-edit Specification

## Purpose
TBD - created by archiving change crewledger-submitter-edit-and-confirmation. Update Purpose after archive.
## Requirements
### Requirement: Editable submitter on receipts
The Edit Receipt form SHALL include an employee dropdown that allows admin/edit users to change the employee assigned to a receipt. The dropdown SHALL list all active employees.

#### Scenario: Reassign receipt to different employee
- **WHEN** an edit-level user changes the employee dropdown on a receipt and saves
- **THEN** the receipt's employee_id SHALL update to the selected employee
- **AND** the receipt_edits audit trail SHALL log the change with field_changed = 'employee_id', old_value = previous employee name, new_value = new employee name

#### Scenario: Employee dropdown shows active employees only
- **WHEN** the edit receipt form is opened
- **THEN** the employee dropdown SHALL contain all employees where is_active = 1
- **AND** the current submitter SHALL be pre-selected

### Requirement: Submitter change via API
The `POST /api/receipts/<id>/edit` endpoint SHALL accept `employee_id` as an editable field.

#### Scenario: API accepts employee_id change
- **WHEN** a POST request includes employee_id with a valid active employee ID
- **THEN** the receipt record SHALL update employee_id to the new value
- **AND** an audit trail entry SHALL be created

