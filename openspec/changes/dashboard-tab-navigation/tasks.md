## 1. CSS Foundation

- [ ] 1.1 Add CSS custom properties for tab bar colors to `:root` in style.css (use existing `--primary` / `--accent` variables, add tab-specific ones if needed)
- [ ] 1.2 Add tab bar styles: `.tab-bar`, `.tab-bar__tab`, `.tab-bar__tab--active`, hover/focus states, mobile-first with 44px min tap target

## 2. Tab Bar Markup & Template

- [ ] 2.1 Define tab config list in the dashboard route (list of dicts with `id` and `label`)
- [ ] 2.2 Add tab bar HTML to `base.html` — render conditionally when `show_tabs` is set, loop over tabs list, highlight active tab
- [ ] 2.3 Update dashboard/ledger route to accept `?tab=` query parameter, default to `ledger`, pass `active_tab` and `tabs` to template

## 3. Tab Content Panels

- [ ] 3.1 Wrap existing ledger content in `ledger.html` inside a tab panel container that shows only when `active_tab == 'ledger'`
- [ ] 3.2 Add Crew tab panel placeholder (empty state with "Crew module coming soon" or ready for Change 2 to populate)
- [ ] 3.3 Handle invalid `?tab=` values by falling back to ledger

## 4. URL & Navigation Wiring

- [ ] 4.1 Tab clicks navigate via `<a href="?tab=<id>">` — server-side rendering, no JS tab switching needed
- [ ] 4.2 Ensure existing nav links (Dashboard, Ledger) route correctly with tab state preserved

## 5. Testing & Verification

- [ ] 5.1 Verify ledger tab renders identically to current ledger page (all filters, sorting, export, modals work)
- [ ] 5.2 Verify crew tab renders and URL shows `?tab=crew`
- [ ] 5.3 Verify invalid tab parameter falls back to ledger
- [ ] 5.4 Run full test suite — all existing tests pass
- [ ] 5.5 Test on mobile viewport (375px) — tabs are tappable and visible without scrolling
