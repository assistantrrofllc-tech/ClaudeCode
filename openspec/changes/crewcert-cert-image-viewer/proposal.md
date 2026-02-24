## Why

Cert documents need to be viewable from the employee detail page. When a manager needs to verify a cert before sending someone to a job site, they should be able to click the document icon and see the actual certificate image/PDF — same pattern as the receipt image viewer in CrewLedger.

## What Changes

- Full-screen modal to display cert document images (JPG, PNG) and PDF first pages
- Cert document serving endpoint with path traversal protection
- Pinch-to-zoom on mobile
- Close button and download button
- Storage at `/opt/crewledger/storage/certifications/<employee_uuid>/`
- Wire document column in cert table to open the modal

## Capabilities

### New Capabilities
- `crewcert-cert-viewer`: Modal-based cert document viewer with image serving and download

### Modified Capabilities

## Impact

- **Routes:** New `/certifications/document/<path>` serving endpoint
- **Templates:** Cert viewer modal added to `crew_detail.html`
- **JS:** Modal open/close logic, pinch-to-zoom
- **CSS:** Reuse existing `.modal` styles
- **Storage:** Cert docs directory structure
