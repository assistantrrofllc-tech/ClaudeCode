# CrewLedger

**The Field Operations Platform for Trades**

CrewLedger is a modular field operations platform that replaces manual receipt tracking, inventory management, and job costing with an automated, text-message-driven system built for trades companies.

---

## What It Does

Employees text a photo of their receipt to a dedicated phone number. The system reads the receipt using AI-powered OCR, confirms the details back via text, categorizes every line item, tags it to a project, and stores everything in a searchable database. Management gets a real-time web dashboard. The accountant gets a weekly email report and one-click QuickBooks export.

No app to download. No login for field crews. Just text a photo.

## Modules

| Module | Description | Status |
|---|---|---|
| **CrewLedger** | Receipt tracking via SMS — OCR, categorization, dashboard, exports | ✅ Complete |
| **CrewCert** | Employee certification tracking — roster, cert CRUD, PDF splitter, CSV import | ✅ Complete |
| **CrewComms** | Cross-channel communication log (SMS, email, calls) | DB scaffold |
| **CrewSchedule** | Crew scheduling and job assignment | Planned |
| **CrewAsset** | Equipment and asset tracking | Planned |
| **CrewInventory** | Shop supply tracking, recurring orders, low stock alerts | Planned |

## How It Works

```
Employee texts receipt photo + project name
        |
        v
  Twilio receives SMS/MMS
        |
        v
  GPT-4o-mini Vision extracts receipt data (OCR)
        |
        v
  Receipt auto-confirmed and saved to SQLite
        |
        v
  Dashboard + Reports + CSV Export
```

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.11+ / Flask |
| Database | SQLite (WAL mode) |
| SMS Gateway | Twilio Programmable Messaging |
| OCR / Vision | OpenAI GPT-4o-mini Vision API |
| Frontend | Mobile-first single-page web dashboard |
| Image Storage | Local filesystem (`storage/receipts/`, `storage/certifications/`) |
| Export | CSV (QuickBooks-compatible), Excel |
| PDF Processing | pdfplumber, pypdf |
| Fuzzy Matching | thefuzz |
| Email Reports | Python SMTP |
| Tunnel (Dev) | ngrok |

## Features

### SMS Receipt Pipeline
- Auto-registration of new employees on first text
- GPT-4o-mini Vision OCR extracts vendor, items, totals, tax, payment method
- Auto-confirm receipts (A2P pending — no outbound SMS confirmation)
- Missed receipt support (manual entry via text)
- Fuzzy project matching against active projects
- Editable submitter with audit trail

### Web Dashboard (Mobile-First)
- **Home** — Week total spend, flagged count, recent activity feed
- **Ledger** — Banking-style transaction table with filters, inline edit, status management
- **Crew** — Employee roster with certification badge summaries, search/filter
- **Crew Detail** — Employee identity card, cert CRUD, document viewer, notes
- **Admin Tools** — PDF cert splitter, bulk CSV cert import with fuzzy name matching
- **Receipt Detail** — Full details with receipt photo, edit form, audit history

### Permissions & Role-Based Access
- 4-tier role system: super_admin > company_admin > manager > employee
- Route-level protection via `@require_role()` decorators on 30+ endpoints
- Module-level access control (none/view/edit/admin) per role
- Data isolation: employee role sees only own receipts and crew record
- Contact masking: phone/email hidden for restricted roles
- User management page (super_admin only) for managing authorized users
- Permission-gated UI: edit/export/admin controls hidden by role

### QuickBooks CSV Export
- One-click export with columns: Date, Vendor, Account, Amount, Tax, Total, Payment Method, Memo, Line Items
- Filterable by date range, employee, project, category

### Weekly Email Reports
- Per-employee breakdown with receipt details
- Flagged receipt alerts
- HTML and plaintext versions

## Project Structure

```
crewos/
├── CLAUDE.md                  # Build spec and session context
├── CHANGELOG.md               # Release history
├── README.md                  # This file
├── requirements.txt           # Python dependencies
├── config/
│   └── settings.py            # Environment variable loading
├── src/
│   ├── app.py                 # Flask application entry point
│   ├── database/
│   │   ├── connection.py      # SQLite connection helper (WAL, Row factory)
│   │   └── schema.sql         # Full database schema + seed data
│   ├── api/
│   │   ├── twilio_webhook.py  # POST /webhook/sms — Twilio inbound
│   │   ├── dashboard.py       # Dashboard routes + APIs (~2300 lines)
│   │   ├── admin_tools.py     # PDF splitter + CSV cert import
│   │   ├── user_management.py # User CRUD (super_admin only)
│   │   └── reports.py         # Weekly report endpoints
│   ├── services/
│   │   ├── ocr.py             # GPT-4o-mini Vision receipt extraction
│   │   ├── permissions.py     # Role hierarchy, access control, decorators
│   │   ├── report_generator.py
│   │   └── email_sender.py
│   └── messaging/
│       └── sms_handler.py     # SMS conversation flow engine
├── dashboard/
│   ├── templates/             # Jinja2 templates (base, index, ledger, crew, etc.)
│   └── static/                # CSS + JS
├── storage/
│   ├── receipts/              # Receipt images (gitignored)
│   └── certifications/        # Cert documents (gitignored)
├── data/                      # SQLite database (gitignored)
├── scripts/
│   └── import_sms_backup.py   # SMS Backup & Restore XML importer
├── legal/                     # Privacy policy, terms (served at /legal/*)
├── tests/                     # 218 pytest tests
└── openspec/                  # Specs and change archives
```

## Getting Started

### Prerequisites

- Python 3.11+
- Twilio account with a phone number (A2P 10DLC registered for US local numbers)
- OpenAI API key (GPT-4o-mini Vision)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/assistantrrofllc-tech/ClaudeCode.git
   cd ClaudeCode
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy the environment template and fill in your keys:
   ```bash
   cp .env.example .env
   ```

   Required environment variables:
   - `TWILIO_ACCOUNT_SID` — Your Twilio Account SID
   - `TWILIO_AUTH_TOKEN` — Your Twilio Auth Token
   - `TWILIO_PHONE_NUMBER` — Your Twilio phone number (E.164 format)
   - `OPENAI_API_KEY` — Your OpenAI API key
   - `APP_PORT` — Server port (default: 5001)

4. Initialize the database:
   ```bash
   python scripts/setup_db.py
   ```

5. Start the server:
   ```bash
   python src/app.py
   ```

6. Open the dashboard at `http://localhost:5001`

### Live Testing with ngrok

To receive real SMS messages from Twilio, you need a public URL:

1. Install ngrok: `brew install ngrok`
2. Sign up at [ngrok.com](https://ngrok.com) and configure your authtoken
3. Start the tunnel: `ngrok http 5001`
4. Copy the HTTPS URL and set it as your Twilio webhook:
   - Go to Twilio Console → Phone Numbers → Your Number
   - Set the webhook URL to: `https://your-subdomain.ngrok-free.dev/webhook/sms`
   - Method: POST

### Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

**218 tests** should pass (1 known skip: openpyxl not installed).

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/webhook/sms` | Twilio inbound SMS/MMS webhook |
| GET | `/health` | Health check |
| GET | `/` | Home screen (HTML) |
| GET | `/api/dashboard/summary` | Home screen data (week totals, breakdowns) |
| GET | `/api/dashboard/flagged` | Flagged receipt queue |
| POST | `/api/dashboard/flagged/<id>/approve` | Approve a flagged receipt |
| POST | `/api/dashboard/flagged/<id>/dismiss` | Dismiss a flagged receipt |
| POST | `/api/dashboard/flagged/<id>/edit` | Edit and approve a flagged receipt |
| GET | `/api/dashboard/search` | Search receipts with filters |
| GET | `/api/dashboard/employee/<id>/receipts` | Employee receipt drill-down |
| GET | `/api/dashboard/receipt/<id>` | Receipt detail with image status |
| GET | `/receipt-image/<id>` | Serve receipt photo |
| GET | `/export/quickbooks` | QuickBooks CSV export |
| GET | `/reports/weekly/preview` | Preview weekly report (HTML) |
| GET | `/reports/weekly/data` | Weekly report data (JSON) |
| POST | `/reports/weekly/send` | Send weekly report email |
| GET | `/admin/users` | User management (super_admin) |
| GET | `/legal/privacy-policy` | Privacy policy (public) |
| GET | `/legal/terms-and-conditions` | Terms and conditions (public) |

## Operating Costs

At full scale (15 employees, ~300 receipts/month):

- Twilio SMS/MMS: ~$15/month
- OpenAI API: ~$2-5/month
- **Total: ~$20/month**

## Build Phases

1. **Phase 1** — Core receipt pipeline: Twilio -> OCR -> save -> dashboard ✅
2. **Phase 2** — Weekly email reports, QuickBooks CSV export ✅
3. **CrewCert** — Employee roster, certification tracking, admin tools ✅
4. **CrewComms** — Communication logging (DB scaffold complete)
5. **Permissions** — 4-tier role-based access control (deployed, live) ✅
6. **Phase 3** — Cost intelligence, anomaly detection, vendor comparison

## License

Proprietary. All rights reserved.
Roofing & Renovations of Florida LLC.

---

*Built by Robert Cordero | Feb 2026*
