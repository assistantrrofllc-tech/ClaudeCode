## Context

CrewLedger already has a receipt image modal (in base.html). CrewCert needs the same pattern for cert documents. The existing modal uses `.modal`, `.modal-backdrop`, `.modal-content` classes. We can reuse this pattern with a separate modal instance for certs.

## Goals / Non-Goals

**Goals:**
- Serve cert document images securely (path traversal protection)
- Modal viewer with close, download, and pinch-to-zoom
- Wire document icon in cert table to open viewer

**Non-Goals:**
- Document upload (part of cert add/edit flow — handle upload in the PDF splitter or manual upload)
- PDF rendering in browser (show first page as image, offer download for full PDF)
- Multi-page document viewer

## Decisions

### 1. Reuse modal CSS pattern, separate modal element

Add a `#cert-doc-modal` to `crew_detail.html` rather than reusing the receipt modal. Keeps separation clean.

### 2. Cert storage path uses employee_uuid

Files stored at `storage/certifications/<employee_uuid>/<cert_type_slug>_<issued_date>.<ext>`. Using UUID avoids exposing sequential IDs in file paths.

### 3. Serve via Flask route, not static files

`/certifications/document/<employee_uuid>/<filename>` — same auth/security pattern as receipt image serving.

## Risks / Trade-offs

- **PDF rendering** — Browser support for inline PDF is inconsistent on mobile. For now, show a download link for PDFs rather than trying to render inline. Can add pdf.js later.
