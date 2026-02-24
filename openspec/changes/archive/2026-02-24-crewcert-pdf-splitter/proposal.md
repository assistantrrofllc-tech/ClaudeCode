## Why

We have multi-page certificate PDFs from Safety Solutions & Supply where each page is one employee's cert. We need a tool to split these into individual pages and assign each to the correct employee — linking the document to their certification record.

## What Changes

- Admin-only route at `/admin/cert-splitter`
- Upload form for multi-page PDF
- System splits PDF into individual pages using pdfplumber/pypdf
- Preview grid shows each page with text extraction for employee name matching
- Admin selects employee per page via dropdown
- "Assign & Save" saves each page to the correct employee's cert storage folder
- Links saved files to existing certification records when cert record exists

## Capabilities

### New Capabilities
- `crewcert-pdf-splitter`: Admin PDF splitting tool with preview, employee assignment, and cert linking

### Modified Capabilities

## Impact

- **Dependencies:** pdfplumber and pypdf added to requirements.txt
- **Routes:** New `/admin/cert-splitter` route (admin only)
- **Templates:** New `cert_splitter.html`
- **Storage:** Individual cert pages saved to employee cert directories
