## Category Management — Deployed

### What Was Built
A defined set of 8 receipt categories with a management page in Settings, receipt-level auto-categorization from OCR, and category dropdowns in all receipt forms.

### The Eight Categories (in dropdown order)
1. Materials — Lumber, concrete, roofing materials, fasteners, adhesives
2. Fuel — Gas stations, diesel, fuel for equipment
3. Food & Drinks — Crew meals, drinks, snacks on the job
4. Tools & Equipment — Hand tools, power tools, equipment purchases
5. Safety Gear — Vests, helmets, harnesses, gloves, eyewear
6. Office & Admin — Printing, office supplies, postage, permits
7. Lodging — Hotels, extended stay for out of town jobs
8. Other — Anything that doesn't fit the above

### Database Changes
- `categories` table: added `is_active` (INTEGER DEFAULT 1) and `sort_order` (INTEGER DEFAULT 0) columns
- `receipts` table: added `category_id` (INTEGER FK → categories.id) — ONE category per receipt, not per line item
- 8 default categories seeded via schema.sql with INSERT OR IGNORE

### OCR Integration
- GPT-4o-mini Vision prompt now includes `"category"` field in JSON output
- Category suggestion based on vendor and line items
- `_resolve_category_id()` in sms_handler.py: fuzzy-matches OCR-suggested category name to categories table
- `_categorize_by_vendor()` in sms_handler.py: vendor-keyword fallback (gas stations→Fuel, Home Depot→Materials, etc.)

### Category Management UI (Settings → Categories)
- Table with Name | Status | Actions columns
- Add Category button — name input, saves via POST /api/categories
- Rename button — prompt with receipt count warning ("X receipts use this category — renaming will update all of them")
- Deactivate button — soft deactivate, hidden from dropdowns, historical receipts unaffected
- Activate button — reactivates deactivated category

### Category Dropdowns
- Edit Receipt modal form: category dropdown populated from GET /api/categories?active=1
- Add Receipt form (ledger page): category dropdown from same API
- Categories cached client-side (`_cachedCategories`), busted on any management action

### API Endpoints Added
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/categories` | GET | List all categories (with `?active=1` filter). Includes receipt_count |
| `/api/categories` | POST | Add new category |
| `/api/categories/<id>` | PUT | Rename category (with duplicate check) |
| `/api/categories/<id>/deactivate` | POST | Soft deactivate |
| `/api/categories/<id>/activate` | POST | Reactivate |

### Tests Added (15 new)
- Default 8 categories seeded on fresh DB
- Category list API (all, active only)
- Add category (success, duplicate rejected, empty name rejected)
- Rename category (success, duplicate name rejected)
- Deactivate category (hidden from dropdowns, receipts keep category_id)
- Activate category (reappears in dropdown)
- Category not found (404 on all operations)
- Receipt edit with category_id
- Settings page shows Categories section
- OCR category field preserved through parsing
- Category names preserved for common vendor types

### Files Changed
- `src/database/schema.sql` — categories table + seed data
- `src/services/ocr.py` — OCR prompt with category field
- `src/messaging/sms_handler.py` — _resolve_category_id(), _categorize_by_vendor()
- `src/api/dashboard.py` — category CRUD endpoints, receipts query joins categories
- `dashboard/static/js/app.js` — category dropdown in edit form, _loadCategories(), _buildCategorySelect()
- `dashboard/templates/settings.html` — category management section
- `dashboard/templates/ledger.html` — category column + badge styling
- `dashboard/static/css/style.css` — .badge--cat styling
- `tests/test_dashboard.py` — 13 new category tests
- `tests/test_ocr.py` — 2 new category parsing tests
- `tests/test_export.py` — updated for new category names/IDs

### Deploy Date
February 23, 2026
