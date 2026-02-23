# CrewLedger — Baseline Spec

**Status:** Deployed to production (Hostinger KVM 2 VPS)
**Version:** 2.1 (Phase 1 + Phase 2B + Category Management)
**Date:** February 2026
**Owner:** Robert Cordero — Tech Quest LLC

---

## 1. System Overview

CrewLedger is a field operations platform for trades companies. Module 1 ("The Ledger") replaces manual receipt collection with an SMS-based system that reads, confirms, categorizes, stores, and reports on every purchase automatically.

Employees text photos of receipts to a Twilio phone number. The system uses GPT-4o-mini Vision to extract structured data, sends a confirmation back via SMS, and saves everything to a SQLite database. Management uses a mobile-first web dashboard for oversight. The accountant receives configurable email reports and can export to QuickBooks.

### Users

| Role | How They Access | What They Do |
|---|---|---|
| **Employees (Field Crew)** | SMS (text messages) | Submit receipts by texting photos with project names |
| **Management** | Web dashboard | Oversee spending, review flagged receipts, manage employees/projects |
| **Accountant** | Email + dashboard | Configurable reports, QuickBooks/CSV/Excel export, receipt image access |

---

## 2. Technology Stack

| Component | Technology | Version |
|---|---|---|
| Backend | Python + Flask | Python 3.11, Flask 3.0+ |
| Database | SQLite | WAL mode, foreign keys enforced |
| SMS Gateway | Twilio Programmable Messaging | twilio SDK 9.0+ |
| Receipt OCR | OpenAI GPT-4o-mini Vision API | openai SDK 1.12+ |
| Image Storage | Local filesystem | `storage/receipts/` |
| Fuzzy Matching | thefuzz + python-Levenshtein | thefuzz 0.22+ |
| Email | Python SMTP (Gmail) | stdlib smtplib |
| Config | python-dotenv | 1.0+ |
| WSGI Server | Gunicorn | 25.1+ |
| Reverse Proxy | Nginx | with Let's Encrypt SSL |
| Process Manager | systemd | auto-restart on failure |
| Frontend | Plain HTML/CSS/JS | No framework, no build step |
| Spec Management | OpenSpec | @fission-ai/openspec |

### Deployed Infrastructure

| Item | Detail |
|---|---|
| **Server** | Hostinger KVM 2 VPS — `srv1306217.hstgr.cloud` (IP: `76.13.109.32`) |
| **App Path** | `/opt/crewledger` |
| **Service** | `systemd` unit: `crewledger.service` |
| **Logs** | `/var/log/crewledger/` |
| **Backups** | `deploy/backup.sh` — SQLite + receipts, 30-day retention |
| **Twilio Number** | +1 (844) 204-9387 |

---

## 3. Database Schema

**10 tables** in SQLite (`data/crewledger.db`), including audit trail and conversation state:

### employees
Phone number is the unique identifier. No passwords, no signup form. Auto-registered on first text. Manageable from dashboard.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| phone_number | TEXT UNIQUE | Employee's permanent ID |
| first_name | TEXT NOT NULL | Extracted from first message |
| full_name | TEXT | Optional |
| role | TEXT | Optional |
| crew | TEXT | Optional |
| employee_uuid | TEXT UNIQUE | UUID identifier |
| photo | TEXT | Path to employee photo |
| is_active | INTEGER | Default 1 |
| created_at | TEXT | datetime |
| updated_at | TEXT | datetime |

### projects
Shared across all modules. Receipt tagging fuzzy-matches against project names. Full CRUD from dashboard.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| project_code | TEXT UNIQUE | Optional project code (e.g., "SPR-001") |
| name | TEXT UNIQUE | Project codename (e.g., "Sparrow") |
| address | TEXT | Job site address |
| city | TEXT | |
| state | TEXT | |
| status | TEXT | `active`, `completed`, `on_hold` |
| start_date | TEXT | Optional |
| end_date | TEXT | Optional |
| notes | TEXT | Free-text project notes |
| created_at | TEXT | datetime |
| updated_at | TEXT | datetime |

### receipts
Core table. One row per receipt submitted via SMS.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| employee_id | INTEGER FK | → employees.id |
| project_id | INTEGER FK | → projects.id (nullable — set to NULL on project delete) |
| category_id | INTEGER FK | → categories.id (one category per receipt) |
| vendor_name | TEXT | From OCR |
| vendor_city | TEXT | From OCR |
| vendor_state | TEXT | From OCR |
| purchase_date | TEXT | YYYY-MM-DD from OCR |
| subtotal | REAL | |
| tax | REAL | |
| total | REAL | |
| payment_method | TEXT | CASH or last 4 digits |
| image_path | TEXT | Local filesystem path |
| status | TEXT | `pending`, `confirmed`, `flagged`, `rejected`, `deleted`, `duplicate` |
| flag_reason | TEXT | Why it was flagged |
| duplicate_of | INTEGER FK | → receipts.id (if marked as duplicate) |
| is_return | INTEGER | 1 if return/refund |
| is_missed_receipt | INTEGER | 1 if no physical receipt |
| matched_project_name | TEXT | Raw text from employee caption |
| fuzzy_match_score | REAL | Match confidence |
| notes | TEXT | Free-text management annotations |
| raw_ocr_json | TEXT | Full GPT response |
| created_at | TEXT | When submitted |
| confirmed_at | TEXT | When employee replied YES |

### line_items
Individual items from a receipt.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| receipt_id | INTEGER FK | → receipts.id (CASCADE delete) |
| item_name | TEXT NOT NULL | From OCR |
| quantity | REAL | Default 1 |
| unit_price | REAL | |
| extended_price | REAL | quantity x unit_price |
| category_id | INTEGER FK | → categories.id |

### categories
Lookup table for receipt-level categorization. Manageable from Settings page. Pre-seeded with 8 defaults (in dropdown order):

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| name | TEXT UNIQUE | Category name |
| description | TEXT | What it covers |
| is_active | INTEGER | Default 1 (soft deactivate) |
| sort_order | INTEGER | Controls dropdown ordering |

**Default categories:**
1. Materials — Lumber, concrete, roofing materials, fasteners, adhesives
2. Fuel — Gas stations, diesel, fuel for equipment
3. Food & Drinks — Crew meals, drinks, snacks on the job
4. Tools & Equipment — Hand tools, power tools, equipment purchases
5. Safety Gear — Vests, helmets, harnesses, gloves, eyewear
6. Office & Admin — Printing, office supplies, postage, permits
7. Lodging — Hotels, extended stay for out of town jobs
8. Other — Anything that doesn't fit the above

**One category per receipt** (not per line item). OCR suggests category, admin can override. Deactivated categories hide from dropdowns but historical receipts keep their label.

### conversation_state
Tracks per-employee SMS conversation flow. One active state per employee.

| Column | Type | Notes |
|---|---|---|
| employee_id | INTEGER FK | → employees.id |
| receipt_id | INTEGER FK | → receipts.id |
| state | TEXT | `idle`, `awaiting_confirmation`, `awaiting_manual_entry`, `awaiting_missed_details` |
| context_json | TEXT | Flow-specific context data |

### receipt_edits
Audit trail for every field change made to a receipt after initial OCR.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| receipt_id | INTEGER FK | → receipts.id (CASCADE delete) |
| field_changed | TEXT NOT NULL | Which field was modified |
| old_value | TEXT | Previous value |
| new_value | TEXT | Updated value |
| edited_at | TEXT | Default datetime('now') |
| edited_by | TEXT | Default 'dashboard' |

### unknown_contacts
Logs SMS attempts from unregistered phone numbers for management review.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| phone_number | TEXT NOT NULL | Sender's number |
| message_body | TEXT | What they sent |
| has_media | INTEGER | Default 0 |
| created_at | TEXT | Default datetime('now') |

### email_settings
Key-value store for accountant-controlled report scheduling.

| Column | Type | Notes |
|---|---|---|
| key | TEXT PK | Setting name |
| value | TEXT | Setting value |
| updated_at | TEXT | Default datetime('now') |

Default keys: `recipient_email`, `frequency` (weekly), `day_of_week` (1=Monday), `time_of_day` (08:00), `include_scope` (all), `include_filter`, `enabled` (1).

### Indexes
- `idx_employees_phone` — unique on phone_number
- `idx_projects_name`, `idx_projects_status`
- `idx_receipts_employee`, `idx_receipts_project`, `idx_receipts_status`, `idx_receipts_vendor`, `idx_receipts_date`, `idx_receipts_created`
- `idx_line_items_receipt`, `idx_line_items_category`, `idx_line_items_name`
- `idx_convo_employee`, `idx_convo_state`
- `idx_receipt_edits_receipt`, `idx_receipt_edits_date`
- `idx_unknown_phone`, `idx_unknown_created`

---

## 4. SMS Receipt Pipeline

### 4.1 Twilio Webhook

**Endpoint:** `POST /webhook/sms`

Receives all incoming SMS/MMS from Twilio. Validates signature, parses message (sender phone, body text, media URLs), routes to SMS handler, returns TwiML response. Unknown senders are logged to `unknown_contacts` table.

**Twilio fields parsed:** `From`, `Body`, `NumMedia`, `MediaUrl0..N`, `MediaContentType0..N`, `MessageSid`, `To`

### 4.2 Employee Auto-Registration

First-time texters are auto-registered by phone number. Name extracted from message using regex patterns:
- "This is Omar" / "My name is Omar" / "I'm Omar" / "Omar here"
- Single word that looks like a name (not a common word)

If no name detected, system asks: "What's your name?"

### 4.3 Receipt Submission Flow

Employee texts `[photo] Project Sparrow`. System:

1. **Downloads** the image from Twilio's media URL (authenticated with SID + token)
2. **Saves** to `storage/receipts/{firstName}_{YYYYMMDD}_{HHMMSS}.jpg`
3. **Sends** image to GPT-4o-mini Vision API with structured extraction prompt
4. **Parses** JSON response: vendor, date, subtotal/tax/total, payment method, line items
5. **Creates** receipt record + line items in database (status: `pending`)
6. **Formats** confirmation message showing extracted data
7. **Sets** conversation state to `awaiting_confirmation`
8. **Sends** confirmation SMS back to employee

### 4.4 Confirmation Flow

Employee replies YES or NO:

**YES** (or Y, YEP, YEAH, CORRECT, LOOKS GOOD, GOOD):
- Receipt status → `confirmed`, `confirmed_at` timestamp set
- Conversation state → `idle`
- Reply: "Saved! Thanks, {name}."

**NO** (or N, NOPE, WRONG, INCORRECT):
- Receipt status → `flagged`, reason: "Employee rejected OCR read"
- Conversation state → `awaiting_manual_entry`
- Reply: Options to re-send photo or text details manually

### 4.5 Manual Entry (after NO)

Employee texts vendor/amount/date manually. System:
- Stores raw text in `context_json`
- Receipt flagged: "Manual entry — needs review"
- Conversation state → `idle`

### 4.6 Missed Receipt Flow

Detected by regex patterns: "didn't get a receipt", "no receipt", "lost receipt", "forgot receipt", "never got receipt"

System:
- Creates receipt with `is_missed_receipt = 1`, status `flagged`
- Asks employee for: store name, approximate amount, items purchased, project name
- Stores details in `context_json`
- Flagged for weekly management review

### 4.7 OCR Processing

**Model:** GPT-4o-mini Vision API
**Input:** Base64-encoded receipt image (JPEG, PNG, GIF, WebP supported)
**Output:** Structured JSON with vendor info, date, amounts, payment method, category suggestion, line items
**Cost:** ~$0.01 per receipt (~$2-5/month at scale)

Response parsing handles:
- Markdown code block wrapping (```json ... ```)
- Numeric field coercion (string → float)
- Missing quantity defaults to 1
- Invalid JSON → returns None, receipt flagged

### 4.8 Confirmation Message Format

```
Ace Home & Supply, Kissimmee FL — 02/18/26 — $100.64
3 items: Utility Lighter ($7.59), Propane Exchange ($27.99), 20lb Propane Cylinder ($59.99)
Project: Sparrow

Is that correct, Omar? Reply YES to save or NO to flag.
```

Line items capped at 5 in the confirmation SMS to keep it readable.

---

## 5. Web Dashboard

Mobile-first web dashboard built with plain HTML/CSS/JS (Jinja2 templates). No React, no build step. All templates extend `base.html` with sticky navigation bar.

### 5.1 Home Page (`/`)

- **Stats row** — 4 cards: This Week spend, This Month spend, Total Receipts, Flagged Count (red highlight when > 0)
- **Flagged Receipts** — Review queue with image button, vendor, employee, flag reason, amount
- **Recent Activity** — Latest receipts with vendor, employee, project, amount, status badge, notes
- **Unknown Contacts** — SMS attempts from unregistered numbers

### 5.2 Ledger Page (`/ledger`)

Banking-style transaction view:
- **Time filters** — All, Today, This Week, This Month, YTD, Custom date range (uses `purchase_date`, not `created_at`)
- **Filters** — Status, Employee, Project dropdowns + Sort/Order controls
- **Totals bar** — Transaction count + total amount
- **Transaction table** — Date, Employee, Vendor, Project, Category (blue badge), Amount, Status, Notes, Image button
- **Inline actions** — Edit (pencil icon) and Delete (trash icon) per row
- **Add Receipt** — Manual entry form with vendor, date, amounts, payment, project, category, employee
- **Export** — QuickBooks CSV, Google Sheets CSV, Excel (.xlsx) dropdown
- **Print** — Print-optimized layout with company header and totals
- **Show Hidden** — Toggle to include deleted/duplicate receipts with Restore option

### 5.3 Employee Management (`/employees`)

- Add new employees (first name, full name, phone, crew, role)
- Search/filter by name or crew
- Activate/deactivate employees
- View last submission date per employee

### 5.4 Settings (`/settings`)

- **Employee Management** link
- **Projects** — Add/edit/remove projects with full metadata (code, address, city, state, status, dates, notes)
- **Categories** — Table with Name/Status/Actions. Add new category, rename (with receipt count warning), deactivate/reactivate. Soft deactivate only — no permanent deletion.
- **Email Reports** — Configure recipient, frequency (daily/weekly/bi-weekly/monthly), day of week, time of day, scope (everyone/specific employee/specific project), enable/disable, send now

### 5.5 Receipt Image Modal

Click any receipt image to view:
- Full-size receipt photo
- Details grid (vendor, date, amounts, payment method, category)
- Notes textarea with inline save
- Line items table
- **Footer actions:** Edit Receipt, Edit History, Confirm (pending/flagged only), Mark Duplicate, Delete, Restore (deleted/duplicate only)
- Edit form includes category dropdown

### 5.6 Dashboard Stats API (`/api/dashboard/stats`)

Returns: week_spend, month_spend, total_receipts, flagged_count, pending_count, confirmed_count, employee_count, project_count, unknown_count. All counts wrapped with COALESCE to handle empty database.

---

## 6. Receipt Editing & Audit Trail

Any receipt field can be edited from the dashboard. Every change is logged to `receipt_edits`:

- **Editable fields:** vendor_name, vendor_city, vendor_state, purchase_date, subtotal, tax, total, payment_method, notes, matched_project_name, project_id, category_id, status, duplicate_of
- **Audit trail:** old_value, new_value, edited_at, edited_by stored per field change
- **Flagged receipt actions:** Approve (→ confirmed), Dismiss (→ rejected), Edit and Approve (edit + confirm in one step)
- **Receipt lifecycle actions:** Confirm (pending/flagged → confirmed), Delete (soft delete, status → deleted), Mark Duplicate (status → duplicate, optional duplicate_of reference), Restore (deleted/duplicate → pending)
- **Conversation state clearing:** When receipts are confirmed/deleted via dashboard, any stuck SMS conversation state is automatically cleared
- **Edit history** viewable per receipt via `/api/receipts/<id>/edits`

---

## 7. Weekly Email Report

### 7.1 Report Generation

**Data aggregation** (`report_generator.py`):
- Queries all receipts for a date range, grouped by employee
- Builds per-employee sections: daily spend summary + full transaction breakdown
- Flagged receipts highlighted separately
- Default range: previous Monday–Sunday

### 7.2 Email Rendering

Two formats generated:
- **HTML:** Professional styled email with header, summary bar (total spend, receipt count, employee count), employee sections, flagged receipt alerts, line item detail
- **Plaintext:** Fallback for email clients that don't render HTML

### 7.3 Report API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/reports/weekly/preview` | GET | Browser-viewable HTML report |
| `/reports/weekly/send` | POST | Send email to accountant (cron-able) |
| `/reports/weekly/data` | GET | Raw JSON report data |

All support `week_start` and `week_end` query params for custom date ranges. The send endpoint also accepts a `recipient` override.

### 7.4 Configurable Delivery

Report scheduling controlled via `email_settings` table (editable from Settings page):
- Frequency: daily, weekly, bi-weekly, monthly
- Day of week, time of day
- Scope: all employees, specific employee, specific project
- Enable/disable toggle
- Cron job: `0 8 * * 1` — sends via `POST /reports/weekly/send`

---

## 8. Export

### 8.1 QuickBooks CSV (`/export/quickbooks`)

- Columns: Date, Vendor, Account (category), Amount, Tax, Total, Payment Method, Memo (Project — Employee), Line Items (pipe-separated)
- Filters: week_start, week_end, employee_id, project, category
- Default range: last Monday–Sunday
- Only includes confirmed and pending receipts

### 8.2 Dashboard Export (`/api/receipts/export`)

Three format options:
- **QuickBooks CSV** — Account column, memo field, pipe-separated line items
- **Google Sheets CSV** — Standard format with all fields
- **Excel (.xlsx)** — Formatted with header styling, auto-width columns, total row, money formatting

Supports all ledger filters (period, date range, employee, project, vendor, status, sort).

---

## 9. API Endpoints Summary

### SMS & Reports
| Endpoint | Method | Purpose |
|---|---|---|
| `/webhook/sms` | POST | Twilio SMS/MMS webhook receiver |
| `/health` | GET | Liveness check: `{"status": "ok"}` |
| `/reports/weekly/preview` | GET | HTML report preview |
| `/reports/weekly/send` | POST | Send weekly email report |
| `/reports/weekly/data` | GET | JSON report data |
| `/export/quickbooks` | GET | QuickBooks CSV export |

### Dashboard Pages
| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Dashboard home page |
| `/ledger` | GET | Banking-style transaction ledger |
| `/employees` | GET | Employee management page |
| `/settings` | GET | Settings page |

### Dashboard API
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/dashboard/stats` | GET | Dashboard summary statistics |
| `/api/dashboard/summary` | GET | Home screen data with breakdowns |
| `/api/dashboard/flagged` | GET | Flagged receipt queue |
| `/api/dashboard/flagged/<id>/approve` | POST | Approve flagged receipt |
| `/api/dashboard/flagged/<id>/dismiss` | POST | Dismiss flagged receipt |
| `/api/dashboard/flagged/<id>/edit` | POST | Edit and approve flagged receipt |
| `/api/dashboard/search` | GET | Advanced search with pagination |
| `/api/dashboard/employee/<id>/receipts` | GET | Employee receipt drill-down |

### Receipts API
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/receipts` | GET | List receipts with filters |
| `/api/receipts` | POST | Manually add a receipt from dashboard |
| `/api/receipts/export` | GET | Export filtered receipts (CSV/Excel) |
| `/api/receipts/<id>` | GET | Receipt detail with line items |
| `/api/receipts/<id>/edit` | POST | Edit receipt with audit trail |
| `/api/receipts/<id>/edits` | GET | Receipt edit history |
| `/api/receipts/<id>/notes` | PUT | Update receipt notes |
| `/api/receipts/<id>/delete` | POST | Soft delete receipt (status → deleted) |
| `/api/receipts/<id>/restore` | POST | Restore deleted/duplicate receipt |
| `/api/receipts/<id>/duplicate` | POST | Mark receipt as duplicate |
| `/receipts/image/<filename>` | GET | Serve receipt image |

### Employees API
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/employees` | GET | List all employees |
| `/api/employees` | POST | Add new employee |
| `/api/employees/<id>` | GET | Employee detail |
| `/api/employees/<id>` | PUT | Update employee |
| `/api/employees/<id>/activate` | POST | Reactivate employee |
| `/api/employees/<id>/deactivate` | POST | Deactivate employee |

### Projects API
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/projects` | GET | List all projects |
| `/api/projects` | POST | Add new project |
| `/api/projects/<id>` | GET | Project detail |
| `/api/projects/<id>` | PUT | Update project |
| `/api/projects/<id>` | DELETE | Delete project (unlinks receipts) |

### Categories API
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/categories` | GET | List all categories (with `?active=1` filter). Includes receipt_count |
| `/api/categories` | POST | Add new category |
| `/api/categories/<id>` | PUT | Rename category (with duplicate check) |
| `/api/categories/<id>/deactivate` | POST | Soft deactivate category |
| `/api/categories/<id>/activate` | POST | Reactivate category |

### Settings API
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/settings` | GET | Get email settings |
| `/api/settings` | PUT | Update email settings |
| `/api/settings/send-now` | POST | Send report immediately |
| `/api/unknown-contacts` | GET | List unknown SMS contacts |

---

## 10. Image Storage

- **Path:** `storage/receipts/` (production: `/opt/crewledger/storage/receipts/`)
- **Naming:** `{firstName}_{YYYYMMDD}_{HHMMSS}.jpg`
- **Download:** Authenticated HTTP GET from Twilio media URLs
- **Serving:** `GET /receipts/image/<filename>` with path traversal protection
- **Persistence:** Every photo saved permanently, tied to receipt record via `image_path`
- **Backup:** Included in `deploy/backup.sh` daily archive

---

## 11. Configuration

All config centralized in `config/settings.py`, read from environment variables (`.env` file):

| Setting | Purpose |
|---|---|
| `TWILIO_ACCOUNT_SID` | Twilio account identifier |
| `TWILIO_AUTH_TOKEN` | Twilio request signing + media auth |
| `TWILIO_PHONE_NUMBER` | Inbound/outbound SMS number |
| `OPENAI_API_KEY` | GPT-4o-mini Vision API access |
| `OLLAMA_HOST` | Local AI host (future use) |
| `OLLAMA_MODEL` | Local AI model (future use) |
| `DATABASE_PATH` | SQLite database file location |
| `RECEIPT_STORAGE_PATH` | Receipt image storage directory |
| `SMTP_HOST/PORT/USER/PASSWORD` | Email sending credentials |
| `ACCOUNTANT_EMAIL` | Weekly report recipient |
| `APP_HOST/PORT/DEBUG` | Flask server binding |
| `SECRET_KEY` | Flask session signing |

---

## 12. Project Structure

```
/opt/crewledger/
├── src/
│   ├── app.py                    # Flask entry point, create_app()
│   ├── api/
│   │   ├── twilio_webhook.py     # POST /webhook/sms
│   │   ├── dashboard.py          # All dashboard routes + API endpoints
│   │   ├── export.py             # GET /export/quickbooks
│   │   └── reports.py            # GET/POST /reports/*
│   ├── database/
│   │   ├── connection.py         # SQLite connection manager
│   │   └── schema.sql            # Full schema (10 tables)
│   ├── messaging/
│   │   └── sms_handler.py        # SMS routing + conversation flow
│   └── services/
│       ├── ocr.py                # GPT-4o-mini Vision integration
│       ├── image_store.py        # Receipt image download + save
│       ├── report_generator.py   # Weekly report data aggregation
│       └── email_sender.py       # HTML/text email rendering + SMTP
├── config/
│   └── settings.py               # Centralized env config
├── scripts/
│   ├── setup_db.py               # DB init + seed script
│   └── load_sample_data.py       # Demo data loader (idempotent)
├── dashboard/
│   ├── static/
│   │   ├── css/style.css         # Mobile-first dashboard styling
│   │   ├── js/app.js             # Receipt modal + client-side logic
│   │   └── images/               # Logos/icons (placeholder)
│   └── templates/
│       ├── base.html             # Master layout + nav + receipt modal
│       ├── index.html            # Dashboard home
│       ├── ledger.html           # Banking-style transaction ledger
│       ├── employees.html        # Employee management
│       └── settings.html         # Settings + projects + email config
├── deploy/
│   ├── setup.sh                  # Full VPS provisioning script
│   ├── update.sh                 # Pull + restart script
│   ├── backup.sh                 # DB + image backup (30-day retention)
│   ├── gunicorn.conf.py          # WSGI server config
│   ├── nginx/crewledger.conf     # Reverse proxy + SSL
│   ├── crewledger.service        # systemd unit file
│   └── .env.production           # Production env template
├── tests/
│   ├── test_ocr.py               # OCR parsing tests
│   ├── test_twilio_webhook.py    # Webhook + SMS tests
│   ├── test_weekly_report.py     # Report generation tests
│   ├── test_dashboard.py         # Dashboard API tests
│   └── test_export.py            # CSV export tests
├── legal/
│   ├── index.html                # Legal landing page
│   ├── privacy-policy.html       # Twilio A2P compliance
│   └── terms.html                # Terms of Service
├── openspec/
│   ├── specs/                    # Living specification documents
│   └── changes/                  # Feature proposals + deltas
├── data/                         # SQLite database (gitignored)
├── storage/receipts/             # Receipt images (gitignored)
├── requirements.txt              # Python dependencies
├── .env                          # Environment config (gitignored)
└── .env.example                  # Config template
```

---

## 13. What Is NOT Built Yet

These are documented in the roadmap (`CREWOS_ROADMAP.md`) but have **no code written**:

- **GitHub Actions CI/CD** — Workflow file exists, needs SSH secrets configured and merge to main
- **Automated Duplicate Detection** — Manual mark-as-duplicate exists, no automatic detection yet
- **Cost Intelligence** — Unit cost tracking, anomaly detection, vendor comparison (Phase 3)
- **Price Comparison** — Google Shopping / Amazon search for line items (Phase 3)
- **Module 2: Inventory Tracker** — Shop supplies, recurring orders, tool inventory (Phase 4)
- **Module 3: Project Management** — Job costing, crew assignment, scheduling (Phase 5)

---

*Baseline spec updated February 23, 2026 | CrewLedger v2.1 | Phase 1 + Phase 2B + Category Management deployed*
