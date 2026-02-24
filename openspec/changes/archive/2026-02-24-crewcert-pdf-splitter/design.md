## Context

Certificate PDFs from Safety Solutions have one cert per page with the employee's name visible. We need to split these into individual files per employee.

## Goals / Non-Goals

**Goals:**
- Upload multi-page PDF and split into individual pages
- Extract text from each page to suggest employee name
- Admin assigns each page to an employee via dropdown
- Saved files linked to cert records automatically

**Non-Goals:**
- Full OCR (use basic text extraction from pdfplumber)
- Automatic name matching without admin review
- Non-admin access to this tool

## Decisions

### 1. Use pdfplumber for text extraction + pypdf for splitting

pdfplumber excels at text extraction from structured PDFs. pypdf handles clean page splitting and saving. Both are lightweight.

### 2. Two-step flow: upload → preview → assign

Step 1: Upload PDF. Step 2: System shows preview grid with extracted names and employee dropdowns. Step 3: Admin clicks "Assign & Save". This prevents mistakes — admin reviews every assignment.

### 3. Save pages as PDF (not converted to image)

Keep the original PDF quality. Each split page saved as a single-page PDF. The cert viewer can display PDFs or convert on the fly later.

### 4. Temporary storage during preview

Uploaded PDF and split pages stored in a temp directory during the preview step. Only moved to permanent storage on "Assign & Save".

## Risks / Trade-offs

- **Text extraction quality** — Depends on PDF structure. If text can't be extracted, admin manually selects from dropdown. No blocking dependency on extraction quality.
