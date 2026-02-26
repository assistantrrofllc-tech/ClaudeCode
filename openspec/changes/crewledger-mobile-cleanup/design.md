## Context

CrewLedger mobile UI has UX issues: cramped table, image overflow, exposed edit history, clipped module names in header. Line items from OCR are not editable. Filters push content below fold. All changes target ≤768px mobile; desktop unchanged.

Current stack: Flask + Jinja2 + vanilla JS + SQLite. No frameworks. All CSS via style.css custom properties.

## Goals / Non-Goals

**Goals:**
- 4-column compact mobile ledger (date, employee, vendor, amount)
- Thumbnail receipt image with fullscreen viewer
- Collapsible filter panel on mobile
- Inline editable line items with audit trail
- Hide edit history button from UI
- Simplified mobile header (no module tabs)
- Verify module access control works

**Non-Goals:**
- Desktop layout changes
- Price tracking / cost intelligence
- Module access management UI
- Receipt-to-vehicle linking

## Decisions

1. **CSS-only compact table** — Use `display:none` on nth-child columns at ≤768px. No JS needed. Same approach as existing column hiding.
2. **Fullscreen viewer as overlay div** — Add a new `#fullscreen-viewer` div to base.html. Uses CSS `position:fixed; inset:0; z-index:2000`. No library — vanilla JS touch events for pinch-zoom.
3. **Filter collapse via JS toggle** — Wrap sort-row in a container, toggle visibility. Time pills stay outside the collapse.
4. **Line item editing uses existing PUT endpoint** — `/api/receipts/<id>/line-items` already exists with audit trail. Just needs the detail card to expose inline editing without the full edit form.
5. **Remove edit history button from template** — Clean removal, not CSS hide. Backend endpoint preserved.
6. **Header responsive via CSS media query** — Hide `.module-bar__tabs` at ≤768px. Brand link goes to `/` (module cards).

## Risks / Trade-offs

- **Pinch-to-zoom complexity** — Implementing native-feel pinch-to-zoom in vanilla JS is non-trivial. Risk: janky zoom behavior. Mitigation: Use CSS `touch-action: pinch-zoom` on the image and let the browser handle native pinch zoom, only add JS for open/close.
- **Filter state persistence** — Collapsing filters means users might forget active filters. Mitigation: Keep summary line visible ("7 transactions — $381.71") and show active filter count on toggle button.
