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
| **The Ledger** | Receipt tracking via SMS — OCR, confirmation, categorization, dashboard | ✅ Complete |
| **Inventory Tracker** | Shop supply tracking, recurring orders, low stock alerts | Planned |
| **Project Management** | Job costing, crew assignment, project timelines | Planned |

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
  Confirmation message sent back via SMS
        |
        v
  Employee confirms via YES/NO reply
        |
        v
  Receipt saved to SQLite with all fields
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
| Image Storage | Local filesystem (`storage/receipts/`) |
| Export | CSV (QuickBooks-compatible) |
| Email Reports | Python SMTP |
| Tunnel (Dev) | ngrok |

## Features

### SMS Receipt Pipeline
- Auto-registration of new employees on first text
- GPT-4o-mini Vision OCR extracts vendor, items, totals, tax, payment method
- Confirmation flow via YES/NO text reply
- Missed receipt support (manual entry via text)
- Fuzzy project matching against active projects

### Web Dashboard (Mobile-First)
- **Home** — Week total spend, comparison vs prior week, flagged count, spend breakdown by crew/card/project, recent activity feed
- **Flags** — Review queue for flagged receipts with approve/edit/dismiss actions
- **Search** — Full-text search with filters (date, employee, project, vendor, category, amount, status), pagination, CSV export
- **Employee Drill-down** — Tap any crew member to see all their receipts
- **Receipt Detail** — Tap any transaction to see full details with the actual receipt photo

### QuickBooks CSV Export
- One-click export with columns: Date, Vendor, Account, Amount, Tax, Total, Payment Method, Memo, Line Items
- Filterable by date range, employee, project, category

### Weekly Email Reports
- Per-employee breakdown with receipt details
- Flagged receipt alerts
- HTML and plaintext versions

## Project Structure

```
crewledger/
├── CLAUDE.md              # Full build specification
├── README.md              # This file
├── .env.example           # Environment variable template
├── .gitignore
├── requirements.txt       # Python dependencies
├── config/
│   └── settings.py        # Environment variable loading
├── src/
│   ├── app.py             # Flask application entry point
│   ├── database/
│   │   ├── connection.py  # SQLite connection helper (WAL, Row factory)
│   │   └── schema.sql     # Full database schema + seed data
│   ├── api/
│   │   ├── twilio_webhook.py  # POST /webhook/sms — Twilio inbound
│   │   ├── dashboard.py       # Dashboard API + receipt image serving
│   │   ├── export.py          # GET /export/quickbooks — CSV export
│   │   └── reports.py         # Weekly report endpoints
│   ├── services/
│   │   ├── ocr.py             # GPT-4o-mini Vision receipt extraction
│   │   ├── report_generator.py
│   │   └── email_sender.py
│   └── messaging/
│       └── sms_handler.py     # SMS conversation flow engine
├── dashboard/
│   └── templates/
│       └── dashboard.html     # Single-page dashboard (HTML + CSS + JS)
├── storage/
│   └── receipts/              # Receipt image files (gitignored)
├── data/                      # SQLite database (gitignored)
├── tests/
│   ├── test_twilio_webhook.py # 11 tests — SMS pipeline
│   ├── test_weekly_report.py  # 12 tests — report generation
│   ├── test_export.py         # 16 tests — CSV export
│   ├── test_dashboard.py      # 25 tests — dashboard API
│   └── test_ocr.py            # 15 tests — OCR parsing
└── scripts/                   # DB setup, seed data, utilities
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

All **79 tests** should pass.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/webhook/sms` | Twilio inbound SMS/MMS webhook |
| GET | `/health` | Health check |
| GET | `/` | Dashboard (HTML) |
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

## Operating Costs

At full scale (15 employees, ~300 receipts/month):

- Twilio SMS/MMS: ~$15/month
- OpenAI API: ~$2-5/month
- **Total: ~$20/month**

## Build Phases

1. **Phase 1** — Core receipt pipeline: Twilio -> OCR -> confirm -> save -> dashboard ✅
2. **Phase 2** — Weekly email reports, QuickBooks CSV export ✅
3. **Phase 3** — Cost intelligence, anomaly detection, vendor comparison
4. **Phase 4** — Module 2: Inventory Tracker
5. **Phase 5** — Module 3: Project Management

## License

Proprietary. All rights reserved.
Roofing & Renovations of Florida LLC.

---

*Built by Robert Cordero | Feb 2026*
