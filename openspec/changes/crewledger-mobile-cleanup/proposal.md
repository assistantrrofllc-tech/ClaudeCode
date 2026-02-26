## Why

The mobile ledger is cramped — 6+ columns squeeze vendor names to 3 lines and cut off amounts ("$12.", "$83."). Receipt images overflow their containers. Filters push content below the fold. Line items from OCR are messy and uneditable. Edit History is exposed to users who don't need it. The header shows module names that get clipped on small screens ("ewCert"). These UX issues make the ledger feel broken on mobile.

## What Changes

- **Compact mobile ledger (≤768px)**: Show only 4 columns (Date mm/dd/yy, Employee first name, Vendor truncated, Amount bold right-aligned). Hide Project, Category, Status, Notes, Actions.
- **Filter collapse on mobile**: Keep time pills visible, collapse sort/filter dropdowns behind a "Filters" toggle button. Summary line always visible.
- **Receipt detail card redesign**: Thumbnail image (30-40% width, object-fit:contain, no overflow), clean two-column detail grid, tappable thumbnail opens full screen viewer.
- **Full screen image viewer**: Dark overlay, object-fit:contain, pinch-to-zoom, close via X or swipe down. Separate layer from detail card — no swipe navigation in viewer.
- **Swipe navigation between receipts**: Left/right swipe on detail card level cycles receipts. Counter updates ("3 of 7"). Arrow buttons as fallback. Existing swipe code already works — verify and enhance.
- **Editable line items**: Inline edit (name, qty, unit price) on detail card. Save writes to line_items table + logs changes in receipt_edits audit trail. Original OCR data preserved in raw_ocr_json.
- **Hide Edit History button**: Remove from receipt detail template entirely (not CSS hide). Keep backend API + data.
- **Header simplification on mobile**: Hide module tab names below 768px. Show only "CrewOS" brand + gear + avatar + sign out.
- **Module access verification**: Confirm super_admin sees all modules, default users see crewcert only. Seed robert.m.cordero@gmail.com as default user.

## Capabilities

### New Capabilities
- `fullscreen-image-viewer`: Full screen receipt image overlay with pinch-to-zoom, dark background, close gestures
- `mobile-filter-collapse`: Collapsible filter panel on mobile with persistent time pills and summary

### Modified Capabilities
- `crewledger-baseline`: Mobile ledger layout changes (4-column compact), receipt detail card redesign, line item editing, edit history removal from UI

## Impact

- **Templates**: `ledger.html`, `base.html` — layout and filter changes
- **CSS**: `style.css` — compact mobile table, filter collapse, fullscreen viewer, header responsive
- **JS**: `app.js` — fullscreen viewer, filter toggle, enhanced line item edit with audit, receipt detail card layout
- **Backend**: Line item PUT endpoint already exists (`/api/receipts/<id>/line-items`). Receipt edit audit trail already exists. No new tables needed.
- **DB**: Seed `robert.m.cordero@gmail.com` into `authorized_users` with default role
- **No breaking changes** — desktop layout unchanged, all existing APIs preserved
