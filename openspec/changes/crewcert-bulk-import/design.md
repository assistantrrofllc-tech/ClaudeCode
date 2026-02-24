## Context

thefuzz is already in requirements.txt for receipt vendor matching. Reuse it for employee name fuzzy matching during CSV import.

## Goals / Non-Goals

**Goals:**
- Parse CSV with columns: Employee Name, Certification Type, Issue Date, Expiry Date, Status, Issuing Org, Notes
- Fuzzy match employee names to roster
- Preview before import with match confidence
- Skip duplicates, flag unmatched rows

**Non-Goals:**
- Automatic import without review
- Custom CSV column mapping

## Decisions

### 1. Two-step flow: upload → preview → import
Same pattern as the PDF splitter. Upload CSV, show preview with match results, admin reviews and clicks Import.

### 2. Fuzzy match with thefuzz using token_sort_ratio
`token_sort_ratio` handles name order differences (e.g. "Martinez Mario" vs "Mario Martinez"). Threshold: 80+ = auto-match, 60-79 = suggest with warning, <60 = unmatched.

### 3. Cert type matching by name
Match cert type from CSV to certification_types table by fuzzy name match.

## Risks / Trade-offs
- Name typos (e.g. "Marvin Marteinz") will show as low-confidence matches. Admin corrects via dropdown.
