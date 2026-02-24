# crewcert-pdf-splitter Specification

## Purpose
TBD - created by archiving change crewcert-pdf-splitter. Update Purpose after archive.
## Requirements
### Requirement: Admin-only PDF splitter page
The system SHALL provide an admin-only page at `/admin/cert-splitter` for uploading and splitting multi-page certification PDFs.

#### Scenario: Access cert splitter
- **WHEN** admin navigates to `/admin/cert-splitter`
- **THEN** the upload form SHALL be displayed

### Requirement: PDF upload and page splitting
The system SHALL accept a multi-page PDF upload, split it into individual pages, and display a preview grid showing each page with extracted text.

#### Scenario: Upload multi-page PDF
- **WHEN** admin uploads a 12-page cert PDF
- **THEN** the system SHALL display 12 preview cards, one per page, with extracted text and employee dropdown

### Requirement: Employee assignment per page
Each preview card SHALL have a dropdown of all active employees. The system SHALL attempt to match extracted text to employee names and pre-select the best match.

#### Scenario: Assign employee to page
- **WHEN** admin selects an employee from the dropdown for a page
- **THEN** the page SHALL be associated with that employee for saving

### Requirement: Save assigned pages to cert storage
Clicking "Assign & Save" SHALL save each assigned page as a single-page PDF to the employee's cert storage directory and link it to their certification record if one exists.

#### Scenario: Save and link
- **WHEN** admin clicks "Assign & Save" with all pages assigned
- **THEN** each page SHALL be saved to `storage/certifications/<employee_uuid>/` and linked to the matching cert record

