# CLAUDE.md — CrewLedger

> Field Operations Platform for Trades — Built by Robert Cordero / Roofing & Renovations of Florida LLC

## Project Overview

CrewLedger is a modular field operations platform built for trades companies. It replaces manual bookkeeping workflows (lost receipts, manual QuickBooks entry, no spend visibility) with automated, text-message-driven systems.

**Business model:** A la carte modules or bundled subscription (CrewLedger Plus).

| Module | Name | Status |
|--------|------|--------|
| Module 1 | The Ledger — Receipt Tracker | Phase 1: Building Now |
| Module 2 | Inventory Tracker | Phase 2: Planned |
| Module 3 | Project Management | Phase 3: Planned |
| Bundle | CrewLedger Plus — All Modules | Future |

**Target market:** Roofing first, but trade-agnostic by design (HVAC, plumbing, electrical, landscaping — any field crew submitting receipts and managing materials).

---

## Architecture Philosophy

- Every module is built standalone first, then integrated into the platform.
- Mobile-first web app — no native iOS/Android apps.
- Local processing on Mac Mini (Ollama) keeps ongoing costs near zero.
- One API call per receipt (GPT-4o-mini Vision) handles cloud intelligence.
- SQLite database, local image storage, Python backend. Simple stack.
- Modules share the same employee registry, project list, and database.

---

## Technology Stack

| Component | Tool | Notes |
|-----------|------|-------|
| SMS / MMS gateway | **Twilio** | Local number, MMS enabled, A2P 10DLC required at scale |
| Receipt OCR | **OpenAI GPT-4o-mini Vision** | One API call per receipt image |
| Data structuring & categorization | **Ollama** (local LLM) | Llama 3 or Mistral, runs on Mac Mini |
| Database | **SQLite** | Local on Mac Mini |
| Image storage | **Local filesystem** | On Mac Mini, backed up |
| Backend / pipeline | **Python** | Watchdog, Flask or FastAPI |
| Dashboard | **Mobile-first web app** | Served from Mac Mini |
| Email reports | **Python** (smtplib or SendGrid) | Weekly automated reports |
| QuickBooks export | **Built into dashboard** | CSV formatted to QB import spec |

---

## Module 1: The Ledger (Receipt Tracker) — Current Focus

### Core Pipeline (End to End)

```
1. RECEIVE  — Employee texts photo + project name → Twilio webhook
2. READ     — Photo sent to GPT-4o-mini Vision → raw text extraction
3. STRUCTURE — Ollama turns extracted text into structured JSON
4. CATEGORIZE — Line items auto-tagged by category (Ollama)
5. PROJECT MATCH — Caption fuzzy-matched against known project list
6. CONFIRM  — System texts employee a confirmation using their name
7. REPLY    — YES saves to database; NO triggers fallback flow
8. STORE    — All data + original receipt image saved permanently
9. REPORT   — Weekly email to accountant; dashboard updated in real time
```

### User Roles

| Role | People | Interface |
|------|--------|-----------|
| Submitters | ~10-15 employees with credit cards | Text message (photo + project name) |
| Management | Robert, Richard, Jake, Eric, Zach | Web dashboard — full view + review queue |
| Accountant | Kim | Weekly email report + dashboard access |
| Owner | Doug | Dashboard — high-level spend visibility |

### Employee Registration

No signup form. First text triggers registration:
- System captures name + phone number from natural language introduction
- Phone number is the permanent ID — no passwords, no logins
- All responses use the employee's first name

### Receipt Data Schema

Every receipt stores these fields:

| Field | Example |
|-------|---------|
| Employee Name | Omar |
| Phone Number | +1 (407) 555-0192 |
| Vendor Name | Ace Home & Supply Center |
| Vendor Address | 7848 W Irlo Bronson Hwy, Kissimmee FL |
| Date & Time | 02/18/2026 1:30 PM |
| Project | Sparrow (fuzzy matched, flagged if uncertain) |
| Category | Materials |
| Line Item Name | Propane Cylinder 20LB (each item stored individually) |
| Quantity | 1 |
| Unit Cost | $59.99 |
| Subtotal / Tax / Total | $95.57 / $5.07 / $100.64 |
| Payment Method | Mastercard ending 7718 |
| Receipt Image | omar_20260218_130000.jpg |
| Status | Confirmed / Flagged / Missed |
| Flag Reason | Fuzzy project match (if applicable) |

### Auto-Categorization Labels

| Category | Examples |
|----------|----------|
| Materials | Lumber, roofing sheets, membrane, caulk, adhesive |
| Fuel / Propane | Gas station, propane tanks, propane exchange |
| Tools | Chalk lines, utility knives, drill bits, safety equipment |
| Fasteners & Hardware | Nails, screws, anchors, staples |
| Office / Admin | Pencils, folders, tape, printer paper |
| Shop Supplies | Rags, gloves, cleaning supplies, water cases |
| Equipment Maintenance | Oil changes, filters, wiper blades, tires |
| Unknown / Review | Anything the system can't confidently categorize |

### Key Behavioral Rules

- **Project fuzzy matching:** Handles typos ("Sarrow" -> "Sparrow"). All fuzzy matches flagged internally for management review — employee is NOT asked to fix it.
- **Duplicate detection:** Compares vendor + amount + date + employee. Near-matches flagged for review, NOT auto-rejected.
- **Returns/refunds:** Handled identically to receipts — system reads negative amounts and logs accordingly.
- **Missed receipts:** Employee texts naturally ("I didn't get a receipt at Home Depot"), system walks them through required fields via text. Saved as MISSED RECEIPT with no image.
- **Image naming:** `employeeName_date_time.jpg` — always saved, tied to employee.

### Fallback Flows

- **NO reply (bad OCR):** System asks for retake with better lighting OR manual text entry of details. Flagged for management review.
- **No receipt obtained:** Guided text flow to capture vendor, amount, items, date manually. Flagged as MISSED RECEIPT.

---

## Dashboard Specifications

### Home Screen
- Last week's total spend — big and prominent at top
- Collapsible breakdown: by crew, by cardholder, by project
- Flagged receipts section — red badge, always visible
- Quick summary tiles: this week vs last week, top vendor, biggest category

### Review Queue
- Fuzzy project matches, NO replies, missed receipts, potential duplicates
- Each item shows: employee name, vendor, amount, flag reason, receipt image
- Management can approve, correct, or dismiss each flag

### Search & Filter
- Filters: date range, employee, project, vendor, category, item name, amount range, status
- Results as clean transaction list with receipt image accessible per row
- Export button on any filtered view — QuickBooks-ready CSV

### Accountant Output (Kim)
- **Weekly email:** Per-employee format ("Here is Omar's week"), daily spend summary + full transaction breakdown, flagged receipts clearly marked
- **Dashboard access:** Filter by date range, employee, project, vendor, category, or item; pull up actual receipt images; generate on-demand reports
- **QuickBooks export:** Single button click, CSV with: date, vendor name, expense account/category, amount, payment method, memo/job code/project

### Cost Intelligence (Long-term)
- Unit cost comparison across vendors after 3-6 months of data
- Recurring purchase detection and reminders
- Anomaly alerts (e.g., "Materials spend 40% above 90-day average")
- Best supplier near project address based on purchase history
- Price comparison via Google Shopping / Amazon search (future, ~2 hours of work once core is built)

---

## Build Order

This is the sequential build order. Each step must work completely before moving to the next.

| # | Task | Notes |
|---|------|-------|
| 1 | Set up Twilio account + phone number | $1.15/mo. Do A2P registration early. |
| 2 | Set up OpenAI API account | Separate from ChatGPT subscription. $10 credit to start. |
| 3 | Set up Ollama on Mac Mini | Llama 3 or Mistral. |
| 4 | Build Twilio webhook receiver (Python) | Receives incoming texts + photos |
| 5 | Build OCR pipeline | Photo -> GPT-4o-mini -> text -> Ollama -> structured data |
| 6 | Build SQLite database schema | All fields from receipt data table |
| 7 | Build employee registration logic | First-contact name capture, phone as ID |
| 8 | Build project fuzzy matching | Match caption to project list, flag uncertain |
| 9 | Build auto-categorization | Line items -> categories via Ollama |
| 10 | Build confirmation text flow | Send summary, handle YES/NO replies |
| 11 | Build fallback flows | NO reply -> retake or manual entry |
| 12 | Build image storage | Save every photo, named systematically |
| 13 | Build weekly email to Kim | Per-employee format, flagged items marked |
| 14 | Build QuickBooks CSV export | Formatted to QB import spec |
| 15 | Build web dashboard | Home screen, review queue, search/filter, export |
| 16 | Test solo (Phase 1) | Robert only, real receipts |
| 17 | Field test (Phase 2) | 3-5 testers, gather feedback |
| 18 | Full rollout (Phase 3) | All cardholders, Kim off the envelopes |

---

## Rollout Phases

| Phase | Who | Success Looks Like |
|-------|-----|--------------------|
| Phase 1 | Robert only | OCR reads correctly, database saves, confirmation texts work |
| Phase 2 | 3-5 field testers | Employees use it without being told twice |
| Phase 3 | All cardholders | Kim stops opening envelopes |
| Phase 4 | Platform launch | First paying customer outside R&R of FL |

---

## Module 2: Inventory Tracker (Planned)

Uses the same pipeline as The Ledger, extended for:
- Shop supplies (rags, water cases, consumables)
- Recurring orders and schedule tracking
- Tool inventory (in shop, checked out, gone)
- Vendor invoices (same photo-in flow, tagged as invoice vs POS receipt)
- Low stock alerts and vendor comparison for bulk orders

## Module 3: Project Management (Planned)

The connective tissue tying all modules together:
- Full project profiles (address, start date, crew assignment, PO numbers)
- Real-time job costing from receipts and invoices
- Crew assignment and scheduling
- Best suppliers near project address (powered by receipt history data)
- Client-facing reporting (optional)

The project list in Module 1 is the same data structure Module 3 builds on.

---

## Development Conventions for AI Assistants

### General Rules
- **Python backend** — use modern Python (3.10+), type hints encouraged
- **FastAPI or Flask** for web backend — FastAPI preferred for new code
- **SQLite** for database — use parameterized queries, never string interpolation for SQL
- **Keep it simple** — this is a small-team product, avoid over-engineering
- **Mobile-first** — all dashboard UI must work on phone screens first, desktop second
- **Store item names in searchable format** from day one (for future price comparison feature)

### Security
- Phone number is the employee ID — validate incoming Twilio requests with signature verification
- Protect the dashboard with authentication (management/accountant roles)
- Never expose API keys in code — use environment variables
- Validate all incoming webhook data from Twilio
- Sanitize all data before database insertion

### Code Organization (Recommended)
```
crewledger/
├── app/                    # Main application
│   ├── __init__.py
│   ├── main.py             # FastAPI/Flask app entry point
│   ├── config.py           # Environment variables, settings
│   ├── database.py         # SQLite connection, schema, migrations
│   ├── models.py           # Data models / Pydantic schemas
│   ├── routes/
│   │   ├── twilio.py       # Twilio webhook handlers
│   │   ├── dashboard.py    # Dashboard API routes
│   │   └── export.py       # CSV export routes
│   ├── services/
│   │   ├── ocr.py          # GPT-4o-mini Vision integration
│   │   ├── structuring.py  # Ollama data structuring
│   │   ├── categorization.py  # Auto-categorization logic
│   │   ├── project_match.py   # Fuzzy project matching
│   │   ├── registration.py    # Employee first-contact registration
│   │   ├── confirmation.py    # SMS confirmation flow
│   │   ├── fallback.py        # Fallback/missed receipt flows
│   │   ├── duplicates.py      # Duplicate detection
│   │   └── reporting.py       # Weekly email generation
│   ├── static/             # Dashboard frontend assets
│   └── templates/          # HTML templates (if using server-side rendering)
├── images/                 # Receipt image storage
├── tests/                  # Test suite
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── README.md
```

### Testing
- Write tests for each pipeline step in isolation
- Test the full pipeline end-to-end with sample receipt images
- Test fuzzy matching with intentional typos
- Test edge cases: blurry photos, partial receipts, no project name, duplicate submissions

### Cost Awareness
- Full-scale operating cost target: ~$20/month (Twilio ~$15 + OpenAI ~$5)
- Minimize OpenAI API calls — one call per receipt, do everything else locally
- Ollama handles structuring, categorization, and any other LLM tasks locally at zero cost

### Commit Messages
- Use clear, descriptive commit messages
- Prefix with the component area: `twilio:`, `ocr:`, `dashboard:`, `database:`, `email:`, etc.
- Example: `ocr: add GPT-4o-mini Vision receipt text extraction`

---

## Employee-Facing Text Message Guidelines

When building SMS flows, follow this tone:
- Use the employee's **first name** in every response
- Keep messages conversational but professional
- Confirmation format:
  ```
  "Vendor, Location — Date — $Total
  N items: Item1 ($X), Item2 ($Y), ...
  Project: ProjectName

  Is that correct, [Name]? Reply YES to save or NO to flag."
  ```
- Never ask the employee to fix fuzzy project matches — flag internally instead
- Missed receipt flow should feel natural, not like filling out a form

---

## Key Design Decisions (Do Not Change Without Discussion)

1. **Phone number as employee ID** — no passwords, no logins, no friction
2. **One OpenAI call per receipt** — everything else runs locally on Ollama
3. **SQLite, not Postgres** — simplicity over scalability at this stage
4. **Fuzzy matches flagged for management, not bounced back to employees** — reduce friction for field workers
5. **Duplicates flagged, not auto-rejected** — smart analysis over aggressive filtering
6. **Image always saved** — serves as audit trail even if data processing fails
7. **Per-employee weekly email format** — "Here is Omar's week", not a giant data dump
8. **CSV export matches QuickBooks import spec exactly** — eliminates manual entry for accountant
