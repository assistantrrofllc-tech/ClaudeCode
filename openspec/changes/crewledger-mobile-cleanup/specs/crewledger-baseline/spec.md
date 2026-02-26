## MODIFIED Requirements

### Requirement: Mobile ledger table layout
The ledger table on mobile (≤768px) SHALL display only 4 columns: Date (mm/dd/yy), Employee (first name), Vendor (truncated with ellipsis), and Amount (bold, right-aligned).

#### Scenario: 4-column mobile layout
- **WHEN** the ledger page loads on a screen ≤768px
- **THEN** only Date, Employee, Vendor, and Amount columns are visible; Project, Category, Status, Notes, and Actions columns are hidden

#### Scenario: Vendor name truncation
- **WHEN** a vendor name exceeds the available column width on mobile
- **THEN** the name truncates with an ellipsis and does not wrap to a second line

#### Scenario: Amount never cut off
- **WHEN** the ledger displays on mobile
- **THEN** the Amount column always shows the full dollar value and is never truncated

### Requirement: Receipt detail card with thumbnail
The receipt detail modal SHALL display the image as a contained thumbnail with clean two-column field layout.

#### Scenario: Thumbnail display
- **WHEN** user taps a receipt row to open the detail card
- **THEN** the receipt image displays as a thumbnail (30-40% width on desktop side panel, contained on mobile) with no overflow

#### Scenario: Tap thumbnail opens fullscreen
- **WHEN** user taps the receipt thumbnail image
- **THEN** the fullscreen image viewer opens

### Requirement: Editable line items on detail card
The receipt detail card SHALL display line items as inline-editable fields.

#### Scenario: Edit line item name
- **WHEN** user taps a line item name in the detail card and changes it
- **THEN** the change is saved via PUT to /api/receipts/{id}/line-items with audit trail in receipt_edits

#### Scenario: Audit trail logging
- **WHEN** a line item is edited
- **THEN** the old and new values are logged in the receipt_edits table with field_changed indicating the line item field

### Requirement: Edit history hidden from UI
The Edit History button SHALL NOT appear in the receipt detail modal template.

#### Scenario: No edit history button
- **WHEN** user opens a receipt detail modal
- **THEN** there is no "Edit History" button visible; the backend API endpoint /api/receipts/{id}/edits remains functional

### Requirement: Mobile header simplified
The module tab bar SHALL hide module tab names on screens ≤768px, showing only the CrewOS brand link, settings gear, user avatar, and sign out.

#### Scenario: Header on mobile
- **WHEN** the page loads on a screen ≤768px
- **THEN** module tab names are hidden and the header shows "CrewOS" (links to /), gear icon, avatar, and sign out icon
