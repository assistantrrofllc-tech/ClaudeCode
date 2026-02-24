## ADDED Requirements

### Requirement: Employee detail page at /crew/<employee_id>
The system SHALL render a detail page at `/crew/<employee_id>` showing the employee's full profile, certification badges, certifications table, and notes section.

#### Scenario: Valid employee ID
- **WHEN** user navigates to `/crew/1`
- **THEN** the employee's identity card, cert badges, cert table, and notes SHALL render

#### Scenario: Invalid employee ID
- **WHEN** user navigates to `/crew/99999` (non-existent)
- **THEN** the system SHALL return a 404 page

### Requirement: Identity card section
The top of the detail page SHALL display: full name, phone (click-to-call), email, crew assignment, role/title, status (Active/Inactive), placeholder avatar, and an "Edit Employee" button.

#### Scenario: Edit employee inline
- **WHEN** user clicks "Edit Employee" and changes fields
- **THEN** the fields SHALL become editable and a "Save" button SHALL persist changes via API

### Requirement: Certification badge row with scroll links
The detail page SHALL display the same color-coded cert badge row as the list view. Clicking a badge SHALL scroll to the corresponding certification in the table below.

#### Scenario: Click badge scrolls to cert
- **WHEN** user clicks the "FP" (Fall Protection) badge
- **THEN** the page SHALL scroll to the Fall Protection row in the certifications table

### Requirement: Certifications table
The detail page SHALL display a table with columns: Cert Type, Issued, Expires, Status, Document, Actions. Each row represents one certification record.

#### Scenario: Cert with valid status
- **WHEN** a certification has expires_at more than 90 days from today
- **THEN** the status column SHALL show a green "Valid" pill

#### Scenario: Cert with document
- **WHEN** a certification has a document_path
- **THEN** the document column SHALL show a clickable icon (wired in Change 4)

### Requirement: Add certification
The detail page SHALL have an "Add Certification" button that opens a form with fields: cert type (dropdown), issued date, expiry date, issuing org, notes.

#### Scenario: Add cert successfully
- **WHEN** user selects a cert type and fills in dates then submits
- **THEN** the certification SHALL be created and appear in the table

### Requirement: Edit and delete certifications
Each cert row SHALL have Edit and Delete action buttons. Edit opens a pre-filled form. Delete soft-deletes (sets is_active=0).

#### Scenario: Delete cert
- **WHEN** user clicks Delete on a certification and confirms
- **THEN** the certification SHALL be soft-deleted and removed from the visible table

### Requirement: Notes section
The bottom of the detail page SHALL have a notes textarea that saves to the employee record.

#### Scenario: Save notes
- **WHEN** user types in the notes field and clicks Save
- **THEN** the notes SHALL persist and appear on next page load
