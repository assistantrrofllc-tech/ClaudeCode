## Why

We have a master CSV spreadsheet with certification data extracted from PDF certs. We need to bulk-import this into the certifications table, matching employees by name (fuzzy match) with admin review before insert.

## What Changes

- Admin CSV import page at `/admin/cert-import`
- Upload CSV, parse rows, fuzzy match employee names
- Preview screen showing each row with match confidence and warnings
- Import with duplicate skip, unmatched row flagging, and summary report

## Capabilities

### New Capabilities
- `crewcert-bulk-import`: CSV certification import with fuzzy matching, preview, and summary

### Modified Capabilities

## Impact

- **Routes:** New `/admin/cert-import` and `/admin/cert-import/upload` and `/admin/cert-import/save`
- **Templates:** New `cert_import.html`
- **Dependencies:** thefuzz (already installed for receipt matching)
