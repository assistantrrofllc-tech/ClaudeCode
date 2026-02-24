## ADDED Requirements

### Requirement: Cert document serving endpoint
The system SHALL serve cert documents at `/certifications/document/<employee_uuid>/<filename>` with path traversal protection. Only files within the employee's cert storage directory SHALL be served.

#### Scenario: Serve valid cert image
- **WHEN** a request is made for a valid cert document path
- **THEN** the file SHALL be returned with appropriate content type

#### Scenario: Block path traversal
- **WHEN** a request contains `..` or path separators in the filename
- **THEN** the system SHALL return 404

### Requirement: Cert document viewer modal
Clicking the document icon on a certification SHALL open a full-screen modal showing the cert image. The modal SHALL have: close button (X), download button, pinch-to-zoom on mobile.

#### Scenario: Open cert image modal
- **WHEN** user clicks the document icon on a cert with a document_path
- **THEN** a modal SHALL open showing the cert document image

#### Scenario: Close modal
- **WHEN** user clicks the X button or backdrop
- **THEN** the modal SHALL close

#### Scenario: Download cert document
- **WHEN** user clicks the download button in the modal
- **THEN** the browser SHALL download the cert document file

### Requirement: Cert storage directory structure
Cert documents SHALL be stored at `storage/certifications/<employee_uuid>/`. Filename format: `<cert_type_slug>_<issued_date>.<ext>`.

#### Scenario: Storage directory exists
- **WHEN** a cert document is referenced
- **THEN** the storage path SHALL follow the `<employee_uuid>/<slug>_<date>.<ext>` convention
