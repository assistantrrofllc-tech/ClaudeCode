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
| **The Ledger** | Receipt tracking via SMS — OCR, confirmation, categorization, dashboard | In Development |
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
  Ollama formats confirmation message
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
| Backend | Python (Flask/FastAPI) |
| Database | SQLite |
| SMS Gateway | Twilio Programmable Messaging |
| OCR / Vision | OpenAI GPT-4o-mini Vision API |
| Local AI | Ollama (Mac Mini) |
| Frontend | Mobile-first web app |
| Image Storage | Local filesystem |
| Export | CSV (QuickBooks-compatible) |
| Email Reports | Python SMTP / SendGrid |

## Project Structure

```
crewledger/
├── CLAUDE.md              # Full build specification
├── README.md              # This file
├── .env.example           # Environment variable template
├── .gitignore
├── config/                # Application configuration
├── src/
│   ├── app.py             # Main application entry point
│   ├── database/          # SQLite schema, models, connection
│   ├── api/               # Twilio webhook, dashboard REST API
│   ├── services/          # OCR, Ollama, receipt processing,
│   │                        categorization, duplicate detection,
│   │                        fuzzy matching, employee registry
│   ├── messaging/         # SMS conversation flow, templates
│   └── reports/           # Weekly email reports
├── dashboard/
│   ├── static/            # CSS, JS, images
│   └── templates/         # HTML templates
├── storage/
│   └── receipts/          # Receipt image files
├── data/                  # SQLite database (gitignored)
├── tests/                 # Test suite
└── scripts/               # DB setup, seed data, utilities
```

## Getting Started

### Prerequisites

- Python 3.11+
- Twilio account with a phone number
- OpenAI API key (GPT-4o-mini Vision)
- Ollama installed locally (Mac Mini recommended)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/assistantrrofllc-tech/ClaudeCode.git
   cd ClaudeCode
   ```

2. Copy the environment template and fill in your keys:
   ```bash
   cp .env.example .env
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   python scripts/setup_db.py
   ```

5. Start the server:
   ```bash
   python src/app.py
   ```

## Operating Costs

At full scale (15 employees, ~300 receipts/month):

- Twilio SMS/MMS: ~$15/month
- OpenAI API: ~$2-5/month
- **Total: ~$20/month**

## Build Phases

1. **Phase 1** — Core receipt pipeline: Twilio -> OCR -> confirm -> save -> dashboard
2. **Phase 2** — Weekly email reports, QuickBooks CSV export
3. **Phase 3** — Cost intelligence, anomaly detection, vendor comparison
4. **Phase 4** — Module 2: Inventory Tracker
5. **Phase 5** — Module 3: Project Management

## License

Proprietary. All rights reserved.
Roofing & Renovations of Florida LLC.

---

*Built by Robert Cordero | Feb 2026*
