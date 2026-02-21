# CrewLedger Phase 1 — Baseline Spec

**Status:** Deployed to production (Hostinger KVM 2 VPS)
**Version:** 1.0
**Date:** February 2026
**Owner:** Robert Cordero — Roofing & Renovations of Florida LLC

---

## 1. System Overview

CrewLedger is a field operations platform for trades companies. Phase 1 ("The Ledger") replaces manual receipt collection with an SMS-based system that reads, confirms, categorizes, stores, and reports on every purchase automatically.

Employees text photos of receipts to a Twilio phone number. The system uses GPT-4o-mini Vision to extract structured data, sends a confirmation back via SMS, and saves everything to a SQLite database. A weekly email report is sent to the accountant automatically.

### Users

| Role | How They Access | What They Do |
|---|---|---|
| **Employees (Field Crew)** | SMS (text messages) | Submit receipts by texting photos with project names |
| **Management (Robert)** | Web dashboard (planned) | Oversee spending, review flagged receipts, cost intelligence |
| **Accountant (Kim)** | Email + dashboard (planned) | Weekly reports, QuickBooks export, receipt image access |

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
| WSGI Server | Gunicorn | 21.2+ |
| Reverse Proxy | Nginx | with Let's Encrypt SSL |
| Process Manager | systemd | auto-restart on failure |

### Deployed Infrastructure

| Item | Detail |
|---|---|
| **Server** | Hostinger KVM 2 VPS — `srv1306217.hstgr.cloud` |
| **App Path** | `/opt/crewledger` |
| **Service** | `systemd` unit: `crewledger.service` |
| **Logs** | `/var/log/crewledger/` |
| **Backups** | `deploy/backup.sh` — SQLite + receipts, 30-day retention |
| **Twilio Number** | +1 (844) 204-9387 |

---

## 3. Database Schema

**7 tables** in SQLite (`data/crewledger.db`):

### employees
Phone number is the unique identifier. No passwords, no signup form. Auto-registered on first text.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| phone_number | TEXT UNIQUE | Employee's permanent ID |
| first_name | TEXT NOT NULL | Extracted from first message |
| full_name | TEXT | Optional |
| role | TEXT | Optional |
| crew | TEXT | Optional |
| is_active | INTEGER | Default 1 |
| created_at | TEXT | datetime |
| updated_at | TEXT | datetime |

### projects
Shared across all modules. Receipt tagging fuzzy-matches against project names.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| name | TEXT UNIQUE | Project codename (e.g., "Sparrow") |
| address | TEXT | Job site address |
| city | TEXT | |
| state | TEXT | |
| status | TEXT | `active`, `completed`, `on_hold` |

### receipts
Core table. One row per receipt submitted via SMS.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| employee_id | INTEGER FK | → employees.id |
| project_id | INTEGER FK | → projects.id |
| vendor_name | TEXT | From OCR |
| vendor_city | TEXT | From OCR |
| vendor_state | TEXT | From OCR |
| purchase_date | TEXT | YYYY-MM-DD from OCR |
| subtotal | REAL | |
| tax | REAL | |
| total | REAL | |
| payment_method | TEXT | CASH or last 4 digits |
| image_path | TEXT | Local filesystem path |
| status | TEXT | `pending`, `confirmed`, `flagged`, `rejected` |
| flag_reason | TEXT | Why it was flagged |
| is_return | INTEGER | 1 if return/refund |
| is_missed_receipt | INTEGER | 1 if no physical receipt |
| matched_project_name | TEXT | Raw text from employee caption |
| fuzzy_match_score | REAL | Match confidence |
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
Lookup table for auto-categorization. Pre-seeded with 7 defaults:
1. Roofing Materials
2. Tools & Equipment
3. Fasteners & Hardware
4. Safety & PPE
5. Fuel & Propane
6. Office & Misc
7. Consumables

### conversation_state
Tracks per-employee SMS conversation flow. One active state per employee.

| Column | Type | Notes |
|---|---|---|
| employee_id | INTEGER FK | → employees.id |
| receipt_id | INTEGER FK | → receipts.id |
| state | TEXT | `idle`, `awaiting_confirmation`, `awaiting_manual_entry`, `awaiting_missed_details` |
| context_json | TEXT | Flow-specific context data |

### Indexes
- `idx_employees_phone` — unique on phone_number
- `idx_projects_name`, `idx_projects_status`
- `idx_receipts_employee`, `idx_receipts_project`, `idx_receipts_status`, `idx_receipts_vendor`, `idx_receipts_date`, `idx_receipts_created`
- `idx_line_items_receipt`, `idx_line_items_category`, `idx_line_items_name`
- `idx_convo_employee`, `idx_convo_state`

---

## 4. SMS Receipt Pipeline

### 4.1 Twilio Webhook

**Endpoint:** `POST /webhook/sms`

Receives all incoming SMS/MMS from Twilio. Validates signature, parses message (sender phone, body text, media URLs), routes to SMS handler, returns TwiML response.

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
**Output:** Structured JSON with vendor info, date, amounts, payment method, line items
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

## 5. Weekly Email Report

### 5.1 Report Generation

**Data aggregation** (`report_generator.py`):
- Queries all receipts for a date range, grouped by employee
- Builds per-employee sections: daily spend summary + full transaction breakdown
- Flagged receipts highlighted separately
- Default range: previous Monday–Sunday

### 5.2 Email Rendering

Two formats generated:
- **HTML:** Professional styled email with header, summary bar (total spend, receipt count, employee count), employee sections, flagged receipt alerts, line item detail
- **Plaintext:** Fallback for email clients that don't render HTML

### 5.3 Report API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/reports/weekly/preview` | GET | Browser-viewable HTML report |
| `/reports/weekly/send` | POST | Send email to accountant (cron-able) |
| `/reports/weekly/data` | GET | Raw JSON report data |

All support `week_start` and `week_end` query params for custom date ranges. The send endpoint also accepts a `recipient` override.

### 5.4 Automated Delivery

Cron job configured: `0 8 * * 1` — sends report every Monday at 8:00 AM via `POST /reports/weekly/send`.

---

## 6. API Endpoints Summary

| Endpoint | Method | Purpose |
|---|---|---|
| `/webhook/sms` | POST | Twilio SMS/MMS webhook receiver |
| `/reports/weekly/preview` | GET | HTML report preview |
| `/reports/weekly/send` | POST | Send weekly email report |
| `/reports/weekly/data` | GET | JSON report data |
| `/health` | GET | Liveness check: `{"status": "ok"}` |

---

## 7. Image Storage

- **Path:** `storage/receipts/` (production: `/opt/crewledger/storage/receipts/`)
- **Naming:** `{firstName}_{YYYYMMDD}_{HHMMSS}.jpg`
- **Download:** Authenticated HTTP GET from Twilio media URLs
- **Persistence:** Every photo saved permanently, tied to receipt record via `image_path`
- **Backup:** Included in `deploy/backup.sh` daily archive

---

## 8. Configuration

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

## 9. Project Structure

```
/opt/crewledger/
├── src/
│   ├── app.py                    # Flask entry point, create_app()
│   ├── api/
│   │   ├── twilio_webhook.py     # POST /webhook/sms
│   │   └── reports.py            # GET/POST /reports/*
│   ├── database/
│   │   ├── connection.py         # SQLite connection manager
│   │   └── schema.sql            # Full schema (7 tables)
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
│   └── setup_db.py               # DB init + seed script
├── dashboard/
│   ├── static/{css,js,images}/   # Frontend assets (placeholder)
│   └── templates/                # Jinja2 templates (placeholder)
├── deploy/
│   ├── setup.sh                  # Full VPS provisioning script
│   ├── update.sh                 # Pull + restart script
│   ├── backup.sh                 # DB + image backup
│   ├── gunicorn.conf.py          # WSGI server config
│   ├── nginx/crewledger.conf     # Reverse proxy + SSL
│   ├── crewledger.service        # systemd unit file
│   └── .env.production           # Production env template
├── tests/
│   ├── test_ocr.py               # OCR parsing tests
│   ├── test_twilio_webhook.py    # Webhook + SMS tests
│   └── test_weekly_report.py     # Report generation tests
├── legal/
│   ├── privacy-policy.html       # Twilio A2P compliance
│   └── terms.html                # Terms of Service
├── data/                         # SQLite database (gitignored)
├── storage/receipts/             # Receipt images (gitignored)
├── requirements.txt              # Python dependencies
├── .env                          # Environment config (gitignored)
└── .env.example                  # Config template
```

---

## 10. What Is NOT Built Yet

These are documented in the master build plan but have **no code written**:

- **Web Dashboard** — Home screen, review queue, search/filter, receipt image viewer
- **QuickBooks CSV Export** — Button on dashboard to export filtered data
- **Project Name Fuzzy Matching** — Logic exists in spec, not wired into receipt flow
- **Duplicate Detection** — No implementation yet
- **Auto-Categorization** — Category table seeded but items not auto-tagged
- **Cost Intelligence** — Unit cost tracking, anomaly detection, vendor comparison
- **Price Comparison** — Google Shopping / Amazon search for line items
- **Module 2: Inventory Tracker** — Shop supplies, recurring orders, tool inventory
- **Module 3: Project Management** — Job costing, crew assignment, scheduling

---

*Baseline spec generated February 2026 | CrewLedger v1.0 | Phase 1 complete*
