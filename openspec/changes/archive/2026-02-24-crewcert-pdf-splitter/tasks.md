## 1. Dependencies

- [ ] 1.1 Add pdfplumber and pypdf to requirements.txt
- [ ] 1.2 Install in venv

## 2. Backend

- [ ] 2.1 Create `/admin/cert-splitter` GET route (render upload form)
- [ ] 2.2 Create `/admin/cert-splitter/upload` POST route (accept PDF, split pages, extract text, return preview data as JSON)
- [ ] 2.3 Create `/admin/cert-splitter/save` POST route (accept assignments, save pages to cert storage, link to cert records)
- [ ] 2.4 Temp file handling for uploaded/split PDFs

## 3. Frontend

- [ ] 3.1 Create `cert_splitter.html` with upload form
- [ ] 3.2 Preview grid: page thumbnails (or page number + extracted text), employee dropdown per page
- [ ] 3.3 "Assign & Save" button with confirmation summary

## 4. Testing

- [ ] 4.1 Test upload endpoint splits PDF correctly
- [ ] 4.2 Test save endpoint writes files and links certs
- [ ] 4.3 Run full test suite
