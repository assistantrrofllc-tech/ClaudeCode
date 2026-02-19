# CREWLEDGER — Master Build Plan

**The Field Operations Platform for Trades**
**Roofing & Renovations of Florida LLC | Feb 2026**
**Built by Robert Cordero**

---

## Part 1 — Platform Overview

CrewLedger is a modular field operations platform built for trades companies. It starts with the problems that cost contractors money every week — lost receipts, manual bookkeeping, no visibility into material costs — and solves them one module at a time.

Each module works as a standalone product. Companies subscribe to what they need. They can start with just receipts and add inventory or project management later. Or they buy the full bundle from day one.

### The Business Model — A La Carte or Full Meal

- **Module 1 — The Ledger:** Receipt tracking via text message. Starts at $X/month.
- **Module 2 — Inventory Tracker:** Shop supply tracking, recurring orders, stock levels. Starts at $X/month.
- **Module 3 — Project Management:** Full project tracking, job costing, crew assignment. Starts at $X/month.
- **CrewLedger Plus:** All three modules bundled at a discount.

> Although built for roofing first, CrewLedger is designed to be trade-agnostic. HVAC, plumbing, electrical, landscaping — any field crew submitting receipts and managing materials is a customer.

### Architecture Philosophy

- Every module is built standalone first, then welded into the platform.
- Mobile-first web app — no separate iOS or Android app to download or maintain.
- Local processing on Mac Mini (Ollama) keeps ongoing costs near zero.
- One API call per receipt (GPT-4o-mini Vision) handles the only thing that truly needs cloud intelligence.
- SQLite database, local image storage, Python backend. Simple stack, easy to maintain.
- Each module shares the same employee registry, project list, and database — data flows between them naturally once connected.

---

## Part 2 — Module 1: The Ledger (Receipt Tracker)

The Ledger is the foundation. It replaces the weekly envelope of crumpled receipts with a text-message-based system that reads, confirms, categorizes, stores, and reports on every purchase automatically.

### The Problem It Solves

- Employees hand in physical receipts weekly in an envelope
- Accountant manually keys everything into QuickBooks — slow, error-prone
- No real-time visibility into what's being spent or where
- No way to compare unit costs across vendors over time
- Receipts get lost, crumpled, or submitted without a project name

### Who Uses It

- **Employees (Field Crew):** Text in receipts from the field via SMS
- **Management (Robert):** Web dashboard for oversight, review, cost intelligence
- **Accountant (Kim):** Weekly reports, QuickBooks export, receipt image access

### Employee Registration — First Contact

No signup form. No account creation. The first time an employee texts in, they introduce themselves naturally:

> "This is Omar, driver for Mario's crew — here's my first receipt" [photo]

- System captures name + phone number and ties them permanently
- Every response from that point uses their first name
- Phone number is their ID — no passwords, no logins, no friction

### Submitting a Receipt

Employee sends one text — photo and project name at the same time:

> [photo] Project Sparrow

System responds with a confirmation:

> "Ace Home & Supply, Kissimmee FL — 02/18/26 — $100.64
> 3 items: Utility Lighter ($7.59), Propane Exchange ($27.99), 20lb Propane Cylinder ($59.99)
> Project: Sparrow
>
> Is that correct, Omar? Reply YES to save or NO to flag."

### Project Name Matching

- Employee includes the project name in the caption of the photo text
- System fuzzy-matches against the known project list — handles typos ("Sarrow" -> "Sparrow")
- Matched name shown in the confirmation so the employee can catch it if wrong
- All fuzzy matches flagged internally for management review — employee is NOT asked to fix it
- Unknown project names flagged for end-of-week manual review

### Fallback Flows

**If Employee Replies NO (bad OCR read):**
- System asks them to retake the photo with better lighting, OR
- Text back the details manually (vendor, amount, items, date)
- Flagged for management review at end of week

**If They Never Got a Receipt:**
- Employee texts in naturally: "I didn't get a receipt at Home Depot"
- System walks them through the required fields via text
- Saved as MISSED RECEIPT — flagged, no image stored
- Still reviewed at end of week

### Duplicate Detection

- System compares vendor + amount + date + employee before saving
- Near-matches are flagged for review — NOT auto-rejected
- Smart analysis to distinguish actual duplicates from legitimately similar receipts

### Auto-Categorization

Every line item is automatically tagged on arrival. Categories include:

- Roofing Materials
- Tools & Equipment
- Fasteners & Hardware
- Safety & PPE
- Fuel & Propane
- Office & Misc
- Consumables (rags, water, tape, etc.)

> As patterns emerge over time, categories can be refined. The system learns your purchasing habits and will flag anomalies — like if you usually buy pencils every 3 months and it's been 4.

### What Gets Stored Per Receipt

- Receipt image (original photo)
- Vendor name
- Vendor location (city, state)
- Date of purchase
- Subtotal, tax, total
- Payment method (cash, card last 4)
- Line items (item name, quantity, unit price, extended price)
- Category (per line item)
- Project name (matched)
- Employee name + phone
- Timestamp received
- Status (confirmed, flagged, pending)
- Flag reason (if applicable)

### Returns & Refunds

- Handled identically to any other receipt — employee photos it, texts it in
- System reads it as a negative amount and logs it accordingly
- No special flow required on the employee side

### Image Storage

- Every photo that comes in is saved permanently, tied to the employee who sent it
- Named systematically: `employeeName_date_time.jpg`
- Accessible from the dashboard — management can pull up the actual image at any time
- Serves as the audit trail even if data entry ever fails

---

## Part 3 — Accountant Output (Kim)

### Weekly Email Report

- Sent automatically every week, organized per employee
- Framed as "Here is Omar's week" — not one giant data dump
- Each section: daily spend summary at top, full transaction breakdown below
- Flagged receipts clearly marked for her attention
- Goal: Kim opens her email Monday morning. Everything is already organized. No envelope, no manual entry.

### Dashboard Access

- Kim gets her own login to the web dashboard
- She can filter by date range, employee, project, vendor, category, or item
- She can pull up the actual receipt image for any transaction
- She can generate on-demand reports for any custom date range or view

### QuickBooks Export

Standard fields Kim is entering into QuickBooks today:

- Date
- Vendor name
- Expense account / category
- Amount (subtotal, tax, total)
- Payment method
- Memo / job code / project

Since all of these are already stored in CrewLedger, the export is a single button click from the dashboard. She filters the view she wants — a week, a project, an employee — and hits Export. She gets a CSV formatted to QuickBooks import standards. It also opens clean in Excel or Google Sheets.

> QuickBooks accepts CSV imports natively. This eliminates her manual entry entirely for any receipts submitted through CrewLedger.

---

## Part 4 — The Web Dashboard

The dashboard is management-only. Mobile-first web app — works from a phone on a jobsite or a desktop in the office. Same view for all management users.

### Home Screen — What You See First

- Last week's total spend — big and prominent at the top
- Collapsible breakdown below: by crew, by cardholder, by project
- Flagged receipts section — red badge, impossible to miss, always visible
- Quick summary tiles: this week vs last week, top vendor this month, biggest spend category

### Review Queue — Flagged Receipts

- Fuzzy project matches, NO replies, missed receipts, potential duplicates — all land here
- Each flagged item shows: employee name, vendor, amount, reason for flag, receipt image
- Management can approve, correct, or dismiss each flag
- Cleared weekly — same cadence as current envelope process

### Search & Filter View

- One unified search screen with flexible filters
- Filter by: date range, employee, project, vendor, category, item name, amount range, status
- Results show as a clean transaction list with the receipt image accessible per row
- Export button on any filtered view — generates QuickBooks-ready CSV instantly

### Cost Intelligence — The Long Game

- After 3-6 months of data: unit cost comparison across vendors
- "Where did we pay the least for 20lb propane in Kissimmee?" — answered from your own history
- Recurring purchase detection: "You usually buy rags every Monday — last order was 3 weeks ago"
- Anomaly alerts: "Materials spend this week is 40% above your 90-day average"
- Future: "Best supplier near Project Sparrow's address based on what you've actually paid"

### Price Comparison (Future Feature)

- When viewing a line item, a Search button lets you check current online pricing
- Pulls a Google Shopping or Amazon search for that exact item
- Helps identify when you're overpaying and who to switch to for the next order

> This is about 2 hours of work once the rest is built. Worth noting early so the database stores item names in a searchable format from day one.

---

## Part 5 — Technology Stack

| Component | Technology |
|---|---|
| Backend | Python (Flask or FastAPI) |
| Database | SQLite |
| SMS Gateway | Twilio (programmable messaging) |
| OCR / Vision | OpenAI GPT-4o-mini Vision API |
| Local AI | Ollama on Mac Mini (confirmation formatting, categorization) |
| Frontend | Mobile-first web app (HTML/CSS/JS or lightweight framework) |
| Image Storage | Local filesystem, systematically named |
| Export | CSV (QuickBooks-compatible) |
| Email Reports | Python SMTP or SendGrid |
| Hosting | Mac Mini (local) — can move to VPS later |

### Twilio Cost Reality Check

At full scale with 15 employees submitting ~5 receipts each per week (300 receipts/month):

- Phone number: $1.15/month
- Receiving 300 photo messages: ~$5.10/month
- Sending 300 confirmation texts + ~100 follow-ups: ~$8.80/month
- Total Twilio: approximately $15/month at full scale
- OpenAI API: approximately $2-5/month for 300 receipt images

**Total operating cost at full 15-employee scale: approximately $20/month.**

### A2P 10DLC Registration

Twilio requires business registration for A2P (Application-to-Person) messaging — this is a carrier compliance requirement, not Twilio's choice. It costs a one-time registration fee (approximately $4-20) and takes a few days to process. This is required before texting employees at scale. Not needed for Phase 1 testing with just your own number.

---

## Part 6 — Rollout Plan

| Phase | Description |
|---|---|
| Phase 1 | Core receipt pipeline: Twilio -> OCR -> confirm -> save -> dashboard |
| Phase 2 | Weekly email reports, QuickBooks CSV export |
| Phase 3 | Cost intelligence, anomaly detection, vendor comparison |
| Phase 4 | Module 2 — Inventory Tracker |
| Phase 5 | Module 3 — Project Management |

### Employee Guidelines

- As soon as you get a receipt — photo it. Before folding, before your pocket, before anything.
- Lay it flat, good light, whole receipt visible in frame.
- Include the project name in the same text as the photo: `[photo] Project Sparrow`
- If the confirmation looks wrong, reply NO and follow the prompts.
- If you didn't get a receipt, text the number and say so — it will walk you through it.
- Keep your physical receipts until further notice — they are your backup.

---

## Part 7 — Module 2: Inventory Tracker (Planned)

The inventory module uses the same pipeline as The Ledger — same phone number, same OCR, same database structure — extended to handle shop supply invoices and recurring stock items.

### What It Tracks

- Shop supplies: rags (6-8 boxes weekly), water cases, consumables
- Recurring orders: items that come in on a schedule
- Tool inventory: what's in the shop, what's checked out, what's gone
- Vendor invoices: same photo-in flow as receipts, tagged as invoice vs POS receipt

### What It Adds

- Recurring purchase recognition — "Rags usually come Monday, it's Wednesday"
- Low stock alerts — "Water cases: last order was 6 weeks ago"
- Vendor comparison for bulk orders — "You paid $X/box at Supplier A vs $Y at Supplier B"
- Shop inventory dashboard — what's on hand, what's low, what needs ordering

> Module 2 is built on the same foundation as Module 1. The receipt pipeline doesn't change — the system just learns to recognize invoice formats and categorize them differently.

---

## Part 8 — Module 3: Project Management (Planned)

The project management module is the connective tissue that ties everything together. Receipts tagged to Project Sparrow automatically appear inside Project Sparrow's page. Inventory used on a job gets logged against that job. The project dashboard shows true job cost in real time.

### What It Adds

- Full project profiles: address, start date, crew assignment, PO numbers
- Real-time job costing: every receipt and invoice tied to a project adds to its running total
- Crew assignment and scheduling
- "Best suppliers near this project address" — powered by 6+ months of receipt data
- Project timeline, milestones, and progress tracking
- Client-facing reporting (optional)

> The project list in Module 1 (used for receipt tagging) is the same data structure Module 3 builds on. Building Module 1 correctly now means Module 3 slots in cleanly later.

---

## Part 9 — Build Order (Start Here)

Build this in order. Each step should work completely before moving to the next.

| Step | What to Build |
|---|---|
| 1 | SQLite database schema — employees, receipts, line items, projects |
| 2 | Twilio webhook — receive incoming SMS + MMS, extract text and image |
| 3 | GPT-4o-mini Vision — send receipt image, get structured JSON back |
| 4 | Ollama — format confirmation message from OCR data |
| 5 | Confirmation flow — send confirmation SMS, handle YES/NO replies |
| 6 | Save to database — store confirmed receipt with all fields |
| 7 | Employee auto-registration — detect new phone numbers, extract name |
| 8 | Project name fuzzy matching — match caption to known project list |
| 9 | Duplicate detection — flag near-matches before saving |
| 10 | Auto-categorization — tag line items on arrival |
| 11 | Image storage — save photos with systematic naming |
| 12 | Web dashboard — home screen, review queue, search/filter |
| 13 | QuickBooks CSV export — from any filtered dashboard view |
| 14 | Weekly email report — automated per-employee summary to accountant |
| 15 | Cost intelligence — unit cost tracking, anomaly detection (Phase 3) |

---

*CrewLedger Master Build Plan v1.0 | Feb 2026 | Roofing & Renovations of Florida LLC | Robert Cordero*
