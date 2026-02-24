# crewcert-bulk-import Specification

## Purpose
TBD - created by archiving change crewcert-bulk-import. Update Purpose after archive.
## Requirements
### Requirement: CSV import page
The system SHALL provide an admin page at `/admin/cert-import` for uploading certification CSV files.

#### Scenario: Access import page
- **WHEN** admin navigates to `/admin/cert-import`
- **THEN** the upload form SHALL be displayed

### Requirement: CSV parsing and fuzzy matching
The system SHALL parse uploaded CSV files and fuzzy-match employee names and cert type names to existing records. Match confidence SHALL be shown per row.

#### Scenario: High confidence match
- **WHEN** a CSV row has employee name "Mario Martinez" and roster has "Mario Martinez"
- **THEN** the match SHALL show as high confidence (green) with the employee pre-selected

#### Scenario: Low confidence match
- **WHEN** a CSV row has employee name "Marvin Marteinz" (typo)
- **THEN** the match SHALL show as low confidence (yellow) with a warning and manual selection dropdown

### Requirement: Duplicate detection
The system SHALL skip rows where the same employee + cert type + issue date already exists.

#### Scenario: Duplicate row
- **WHEN** a CSV row matches an existing certification record
- **THEN** the row SHALL be marked as "Skip — duplicate" in the preview

### Requirement: Import with summary
After import, the system SHALL show a summary: X imported, X skipped (duplicates), X need review (unmatched).

#### Scenario: Import complete
- **WHEN** admin clicks Import and the process completes
- **THEN** a summary SHALL display counts and details of each outcome

