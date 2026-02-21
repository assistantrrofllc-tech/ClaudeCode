# CREWLEDGER — Phase 2 Build Instructions

**Claude Desktop Instruction File | Feb 2026 | Robert Cordero**

> Read this entire document before touching any files. Phase 1 is complete and live on the Hostinger VPS. You are building Phase 2 additions on top of a working system. Do not rebuild anything that already works.

---

## 1. Current State — What Is Already Live

CrewLedger Phase 1 is fully deployed and running at https://srv1306217.hstgr.cloud

| Component | Status | Notes |
|---|---|---|
| Receipt pipeline — Twilio -> OCR -> DB | Live | Working end to end |
| SMS conversation flows | Live | All 7 scenarios handled |
| GPT-4o-mini Vision OCR | Live | Reading receipts correctly |
| SQLite database | Live | All tables, indexes, categories |
| Receipt image storage | Live | Images saved, not displaying in dashboard yet |
| Weekly email report | Live | Auto-sends Monday 8am |
| QuickBooks CSV export | Live | One button export |
| Web dashboard — home screen | Live | Spend breakdown, flagged queue, recent activity |
| SSL certificate | Live | Let's Encrypt, auto-renews |
| 54 tests passing | Live | Full test suite green |
| A2P 10DLC campaign | Pending | Submitted — waiting Twilio approval, 2-3 weeks |

> The A2P campaign is pending approval. Outbound SMS is currently blocked by Twilio carriers. Incoming webhooks work fine. Do not attempt to fix this — it is a carrier approval process, not a code issue.

---

## 2. Phase 2 — What To Build

| Priority | Feature | Location |
|---|---|---|
| 1 | Fix receipt images — clickable, opens full image | Dashboard + image serving |
| 2 | Employee whitelist — unknown numbers flagged, no response | SMS handler + new DB table |
| 3 | Employee management page — add/edit employees from dashboard | New dashboard page |
| 4 | Ledger page — banking style transaction view | New dashboard page |
| 5 | Ledger time filters — Today, This Week, This Month, YTD, Custom | Ledger page |
| 6 | Ledger sort — by crew, person, card, project, vendor, category | Ledger page |
| 7 | Print view — official formatted report from ledger | Ledger page |
| 8 | Export formats — Excel, Google Sheets CSV, QuickBooks | Ledger page |
| 9 | Email settings — Kim controls schedule and destination | Settings on ledger page |
| 10 | Deploy updates to VPS | Server |

---

## 3. Feature 1 — Clickable Receipt Images

Receipt images are stored on the server but not displaying in the dashboard. Fix this and make them clickable.

### What Needs To Happen

- Serve receipt images from the VPS storage directory via a Flask route
- In the dashboard, every receipt row should have a thumbnail or camera icon
- Clicking it opens a modal or full screen view of the actual receipt photo
- Modal should show the image plus the key fields — vendor, date, total, employee, project
- Works on mobile — pinch to zoom on the image

### Technical Details

- Images are stored at: `/opt/crewledger/storage/receipts/`
- Add a Flask route: `GET /receipts/image/<filename>` that serves the file
- Protect the route — only accessible when logged into the dashboard
- In the dashboard JS, clicking a receipt row calls this endpoint and displays the image

> This is the most important fix. Kim needs to be able to pull up the actual receipt image on demand. Without this the dashboard is incomplete.

---

## 4. Feature 2 — Employee Whitelist Security

Only pre-registered phone numbers should be able to interact with the system. Unknown numbers get no response and trigger a management alert.

### How It Works

- Create an employees table if not already exists — phone number, name, crew, status (active/inactive)
- Every incoming SMS — check the sender's number against the employees table first
- If the number is NOT in the table — do not respond at all, flag it in the dashboard
- Flag shows in the review queue: "Unknown number +1XXXXXXXXXX attempted contact at [time]"
- Management can then add that number as a new employee from the dashboard
- If the number IS in the table — proceed with normal SMS conversation flow

### Why This Matters

- Prevents prompt injection attacks — unknown parties cannot interact with the AI pipeline
- Keeps the system clean — only authorized employees submitting receipts
- Gives management full control over who has access

> Do not send any response to unknown numbers — not even an error message. Complete silence is the correct behavior. Any response creates a potential attack surface.

---

## 5. Feature 3 — Employee Management Page

Management needs to add, edit, and deactivate employees directly from the dashboard without touching the terminal or database.

### Page Layout

- List of all registered employees — name, phone number, crew, status, date added
- Add Employee button — opens a form: name, phone number, crew assignment
- Edit button per employee — update any field
- Deactivate button — marks employee inactive, they can no longer submit receipts
- Reactivate button for inactive employees
- Search/filter by name or crew

### Employee Fields to Store

| Field | Type | Notes |
|---|---|---|
| id | Integer primary key | Auto increment |
| name | Text | First name or full name |
| phone_number | Text unique | E.164 format — +1XXXXXXXXXX |
| crew | Text | Crew or team name |
| role | Text | Driver, foreman, PM, etc. |
| status | Text | active / inactive |
| registered_at | Datetime | When they were added |
| last_submission | Datetime | Last receipt submitted |

> The employee table is shared infrastructure — CrewCert (the certification module) will pull from this same table. Build it right the first time.

---

## 6. Feature 4 — The Ledger Page

A banking-style transaction ledger. This is Kim's primary working view. It should feel familiar — like any accounting software she's used before. Intuitive, clean, no learning curve.

### Design Philosophy

- Feels like E-Trade or a bank statement — not a custom app
- Every transaction on one line with key info visible at a glance
- Click any row to expand and see full details including the receipt image
- Sort and filter without page reloads — fast and responsive
- Mobile friendly but optimized for desktop since Kim likely uses a computer

### Time Frame Filter — Top of Page

| Button | What It Shows |
|---|---|
| Today | All transactions from today |
| This Week | Current week Monday to today |
| This Month | Current calendar month |
| Year to Date | January 1 to today |
| Custom Range | Date picker — from/to dates |

### Sort Options

- Date — newest first by default
- Employee / Crew member
- Crew
- Card — payment method
- Project
- Vendor
- Category
- Amount — highest to lowest or lowest to highest
- Status — confirmed, pending, flagged, missed

### Transaction Row — What Each Line Shows

| Column | Example | Notes |
|---|---|---|
| Date | Feb 18, 2026 | |
| Employee | Omar | |
| Vendor | Ace Home & Supply | |
| Project | Sparrow | |
| Category | Materials | Color coded badge |
| Amount | $100.64 | Bold |
| Status | Confirmed | Green/yellow/red badge |
| Receipt | Camera icon | Click to view image |

### Expanded Row — On Click

- Full vendor details — address, phone
- All line items with quantity and unit price
- Tax and subtotal breakdown
- Payment method
- Full size receipt image
- Flag or edit buttons for management

---

## 7. Feature 5 — Print and Export

### Print View

- Print button at top of ledger page
- Generates a clean formatted report — not just a screenshot of the screen
- Report header: CrewLedger, company name, date range, generated date
- Transactions in a clean table — same columns as the ledger view
- Totals at the bottom — subtotal, tax, grand total
- Category breakdown summary at the end
- Uses browser print dialog — works on any device

### Export Formats

| Format | Button Label | Notes |
|---|---|---|
| Excel (.xlsx) | Export to Excel | Full transaction data with formatting |
| Google Sheets CSV | Export to Google Sheets | CSV formatted for Google Sheets import |
| QuickBooks CSV | Export to QuickBooks | Formatted to QuickBooks expense import spec |

> All exports apply the current filters — if Kim is viewing Project Sparrow for this month, the export contains exactly that data.

---

## 8. Feature 6 — Email Settings

A small settings section on the ledger page — or accessible via a settings icon — where Kim controls her own email reports.

### Settings Kim Can Control

- Email address — where reports get sent
- Frequency — Daily, Weekly, Bi-weekly, Monthly, or Off
- Day and time — if weekly, which day and what time
- What to include — Everyone, Specific crew, Specific employee, Specific project
- Send now button — triggers an immediate report with current filters

> Kim should never have to ask Robert to change her email settings. She controls it herself from the dashboard. This is her tool.

---

## 9. CrewCert Foundation — Plant the Seeds Now

CrewCert is the next module — employee certifications tracked via QR code. We are not building it in Phase 2 but the employee database we build now must support it.

### What CrewCert Will Need From the Employee Table

- Employee ID — unique identifier tied to their QR code
- Name and photo — headshot stored per employee
- Phone number — already being stored
- Crew and role — already being stored
- Certifications will be a separate linked table — cert name, issue date, expiry date, document

### What To Do Now

- Add a `photo` field to the employees table — nullable for now
- Add an `employee_id` field that will become the QR code target
- Create a placeholder `GET /employees/<id>` endpoint that returns employee data as JSON
- This endpoint becomes the QR code landing page in CrewCert

> Do not build the full CrewCert module now. Just make sure the employee table structure supports it without a painful migration later.

---

## 10. Deploying Updates to the VPS

After completing each feature, deploy to the live server using the update script.

### Deployment Steps

1. Make changes locally and run the full test suite — all tests must pass
2. Commit and push to GitHub main branch
3. SSH into the VPS: `ssh root@76.13.109.32`
4. Run the update script: `bash /opt/crewledger/deploy/update.sh`
5. Verify the service restarted: `systemctl status crewledger`
6. Check the health endpoint: `https://srv1306217.hstgr.cloud/health`
7. Confirm with Robert before moving to the next feature

### Useful Server Commands

| Command | What It Does |
|---|---|
| `systemctl status crewledger` | Check if service is running |
| `systemctl restart crewledger` | Restart the service |
| `journalctl -u crewledger -f` | Live logs — watch incoming requests |
| `bash /opt/crewledger/deploy/update.sh` | Pull latest from GitHub and restart |
| `bash /opt/crewledger/deploy/backup.sh` | Backup database and receipt images |

---

## 11. Rules — Non-Negotiable

- Run the full test suite before starting. All 54 tests must pass.
- Do not modify Phase 1 code unless explicitly required by a Phase 2 feature.
- Add tests for every new feature you build.
- Commit and push after each completed feature.
- Deploy and verify on the VPS after each feature.
- Confirm with Robert before moving to the next feature.
- Never hardcode credentials. Always use environment variables.
- Mobile first on all UI work.
- The ledger should feel like accounting software — not a custom app.

---

*CrewLedger Phase 2 Instructions | Feb 2026 | Robert Cordero | Tech Quest LLC*
