# CrewOS — Full System Roadmap

**Modular Field Operations Platform for Small Business**
**Tech Quest LLC | Robert Cordero | Feb 2026**

> This is the living roadmap for CrewOS. Update it as modules are completed and priorities shift. Every chat, every Claude session, every build decision should reference this document.

---

## The Vision

CrewOS is a modular field operations platform built for small businesses — starting with trades companies. Companies subscribe to the modules they need and nothing more. Every module is useful on its own and more powerful together.

The platform is built a la carte. A landscaping company might only need CrewLedger and CrewSchedule. A roofing company might want everything. They pay for what they use.

The employee database is the connective tissue. Every module shares it. Build it right in CrewLedger and every module that comes after snaps in cleanly.

The goal is not to build the most feature-rich platform. The goal is to build the most useful one. If it saves people time and makes their operation easier to run — it wins.

---

## The Module Map

| # | Module | What It Does | Status |
|---|---|---|---|
| 1 | **CrewLedger** | Receipt and expense tracking via SMS | **Phase 1 Live** |
| 2 | **CrewCert** | Employee certifications and QR ID cards | Planned — Next |
| 3 | **CrewAsset** | Asset tracking — gear, tools, safety equipment | Planned |
| 4 | **CrewMaintenance** | Equipment maintenance logs and schedules | Planned |
| 5 | **CrewSchedule** | Job and crew scheduling | Planned |
| 6 | **CrewGroup** | Project management and job costing | Planned |

---

## MODULE 1 — CREWLEDGER

Receipt and expense tracking via SMS. Employees text photos of receipts. The system reads them, confirms with the employee, stores everything, and reports to management and accounting.

### Phase 1 — Complete

| Feature | Status |
|---|---|
| SMS receipt submission via Twilio | Live |
| GPT-4o-mini Vision OCR | Live |
| Employee registration via first text | Live |
| Project fuzzy matching | Live |
| YES/NO confirmation flow | Live |
| Missed receipt flow | Live |
| SQLite database — all tables | Live |
| Receipt image storage | Live |
| Weekly email report — Kim | Live — Monday 8am auto |
| QuickBooks CSV export | Live |
| Web dashboard — home screen | Live |
| SSL + VPS deployment | Live — srv1306217.hstgr.cloud |
| 54 tests passing | Live |
| A2P 10DLC campaign | Submitted — pending Twilio approval |

### Phase 2A — Proof Ledger (Current Priority)

| Feature | Priority |
|---|---|
| Receipt images — clickable, modal view | Build first |
| Employee whitelist — unknown numbers silenced and flagged | Build second |
| Employee management page — add/edit/deactivate from dashboard | Build third |
| Ledger page — banking style, time filters | Build fourth |
| QuickBooks export wired to current ledger filters | Build fifth |

### Phase 2B — Polish (After 2A Is Stable)

- Advanced sort on ledger — crew, card, project, vendor, category, amount
- Print-formatted official report
- Excel export (.xlsx)
- Google Sheets CSV variant
- Email schedule settings — Kim controls frequency and destination from dashboard

### Phase 2C — CrewCert Foundation

- Confirm employee_id UUID field exists
- Confirm photo field exists and is nullable
- Placeholder GET /employees/<id> endpoint for future QR landing page

### Phase 3 — Intelligence (Long Game)

- Unit cost tracking — price history per item per vendor
- Anomaly detection — flags unusual purchases
- Vendor comparison — where did we pay least for X near Project Y
- Recurring purchase detection
- Cost trends and category reports over time

---

## MODULE 2 — CREWCERT

Employee certification tracking and QR ID cards. Safety managers scan a QR code to instantly pull up an employee's certifications, photo, and expiration dates. Built on the employee database from CrewLedger.

### Core Features

- Employee QR code — unique per employee, tied to employee_id UUID
- QR scan opens a mobile-friendly page — name, photo, certifications, expiry dates
- Certification types — OSHA 10, OSHA 30, First Aid, Fall Protection, equipment licenses, etc.
- Expiration tracking — flags certs expiring within 30/60/90 days
- Document storage — upload cert documents per employee
- Management dashboard — see all certs, filter by expiring soon, by crew, by cert type
- Auto-alerts — email or SMS when a cert is approaching expiry
- QR code printable on ID card format

### Shared From CrewLedger

- Employee database — name, phone, crew, role, photo, employee_id
- Management dashboard framework
- VPS infrastructure and deployment pipeline

### What Gets Built New

- Certifications table — cert_type, issue_date, expiry_date, document_path, employee_id
- QR code generation per employee
- Public-facing employee card page — accessible via QR scan, no login required
- Cert management page in dashboard — add, renew, deactivate certs
- Expiry alert system

> CrewCert is the module that makes the employee database feel like a real system. Once a company has QR cards for every employee, they are locked in. High retention value.

---

## MODULE 3 — CREWASSET

Asset tracking for everything a company owns and issues to employees — tools, safety gear, equipment, vehicles. Know who has what, when they got it, when it needs to come back or be replaced.

### Core Features

- Asset catalog — every tool, piece of gear, or equipment in the company
- Issue tracking — who has what, when it was issued, when it is due back
- Safety gear expiration — harnesses, helmets, gloves — when do they need to be replaced
- Asset condition log — new, good, worn, needs replacement
- Photo per asset — visual record
- QR code per asset — scan to see history and current holder
- Low stock alerts — running low on safety glasses, gloves, etc.
- Check-in / check-out flow — employee scans QR, confirms receipt
- Management dashboard — full asset inventory, who has what, what is overdue

### Shared From Previous Modules

- Employee database — link assets to real employees
- QR code infrastructure from CrewCert
- Dashboard and VPS framework

> Safety gear expiration is the killer feature here. OSHA compliance requires tracking this. No one does it well. CrewAsset makes it automatic.

---

## MODULE 4 — CREWMAINTENANCE

Equipment maintenance logs and service schedules. Track every piece of equipment — when it was last serviced, what was done, what is coming due. Never miss a service interval again.

### Core Features

- Equipment catalog — every vehicle, machine, and major tool
- Maintenance log — date, technician, work performed, parts used, cost
- Service schedule — mileage-based or time-based intervals
- Upcoming service alerts — 30/60/90 day warnings
- Document storage — service records, warranties, manuals
- Photo log — before and after service photos
- Cost tracking — maintenance cost per asset over time
- QR code per piece of equipment — scan to see full service history
- Management dashboard — all equipment, service status, upcoming due

### Shared From Previous Modules

- Employee database — who performed the service
- Asset framework from CrewAsset
- QR code infrastructure
- Cost tracking patterns from CrewLedger

> For a roofing company, the trucks and equipment are everything. A missed oil change or failed inspection is a job site shutdown. CrewMaintenance makes this impossible to miss.

---

## MODULE 5 — CREWSCHEDULE

Job and crew scheduling. Who is working where, on what job, with what crew. Mobile-first so field employees can see their schedule from their phone. Replaces Google Sheets and paper schedules.

### Core Features

- Job calendar — all active jobs, who is assigned, what days
- Crew assignment — assign employees to jobs by day or week
- Employee view — each employee sees only their own schedule on mobile
- Schedule changes — push notifications when schedule changes
- Availability tracking — who is available, who is out
- Job address integration — one tap to navigate to job site
- Time tracking — clock in and out per job site
- Overtime alerts — flag employees approaching overtime
- Management view — full team calendar, drag and drop scheduling

### Shared From Previous Modules

- Employee database — full crew roster
- Project data from CrewGroup
- Mobile-first dashboard framework

---

## MODULE 6 — CREWGROUP

Full project management and job costing. Track every job from estimate to completion. Know exactly what each job costs in labor, materials, and overhead. The most complex module — built last when the foundation is solid.

### Core Features

- Job setup — address, scope, start date, end date, contract value
- Budget tracking — estimated vs actual cost per job
- Labor cost — pull from CrewSchedule time tracking
- Material cost — pull from CrewLedger receipts tagged to the job
- Equipment cost — pull from CrewMaintenance and CrewAsset
- Subcontractor tracking — invoices, payments, scope
- Progress photos — upload from job site
- Punch list — outstanding items before job close
- Profitability report — per job, per crew, per month
- Customer record — contact info, job history, warranty dates

### Why This Is Last

CrewGroup is the most complex module and also the most dependent on the others. It pulls data from every other module to produce job costing. Building it first would be a mistake — the foundation has to exist before the analysis can run.

---

## Build Timeline

| Phase | Module | Target | Milestone |
|---|---|---|---|
| Phase 1 | CrewLedger | **Complete** | Receipt pipeline live on VPS |
| Phase 2A | CrewLedger | Weekend target | Proof Ledger — Dashboard -> Ledger -> Click -> Export |
| Phase 2B | CrewLedger | After 2A stable | Polish — sort, print, Excel, email settings |
| Phase 2C | CrewLedger | With 2B | Plant CrewCert hooks in employee table |
| Phase 3 | CrewLedger | After full rollout | Price intelligence, anomaly detection |
| Module 2 | CrewCert | After Ledger stable | QR cards, cert tracking, expiry alerts |
| Module 3 | CrewAsset | After CrewCert | Asset catalog, issue tracking, safety gear expiry |
| Module 4 | CrewMaintenance | After CrewAsset | Equipment logs, service schedules |
| Module 5 | CrewSchedule | Parallel with Maintenance | Job calendar, crew assignment, mobile view |
| Module 6 | CrewGroup | Last | Full project management, job costing, profitability |

> This timeline is intentionally loose. Each phase moves when the previous one is stable and trusted in the real world — not when the code is written. Code is not done until Kim and the field crew are using it without issues.

---

## Technical Foundation

| Layer | Technology | Notes |
|---|---|---|
| Language | Python / Flask | Consistent across all modules |
| Database | SQLite -> PostgreSQL | SQLite now, migrate when multi-tenant or scale requires it |
| SMS | Twilio -> Telnyx | Twilio now, migrate to Telnyx at scale for 30-70% cost savings |
| OCR | GPT-4o-mini Vision | One API call per receipt, ~$2-5/month at current scale |
| Hosting | Hostinger KVM 2 VPS | srv1306217.hstgr.cloud — renew before Feb 28 |
| Deployment | GitHub -> update.sh | Push to GitHub, run one script, live in seconds |
| Frontend | Plain HTML/CSS/JS | No React, no build step — keeps it simple and fast |
| SSL | Let's Encrypt | Auto-renews — never touch it |
| Email | Gmail SMTP | assistant.rrofllc@gmail.com — upgrade to SendGrid at scale |
| Spec management | OpenSpec | Spec-driven development — proposals before code |
| Version control | GitHub | assistantrrofllc-tech/ClaudeCode |
| Domain | techquest-ai.com | Hostinger — auto-renewal OFF — turn it on now |

---

## Business Model

A la carte subscription. Companies pay for the modules they use. Everything is included in the platform but access is gated by subscription tier.

| Module | Standalone Value Prop | Why They Buy It |
|---|---|---|
| CrewLedger | Stop the envelope. Digital receipts, automatic reports. | Kim stops doing data entry. Doug sees where money goes. |
| CrewCert | OSHA compliance without spreadsheets. | One scan, full cert history. Safety manager loves it. |
| CrewAsset | Know where everything is and who has it. | Stop buying tools twice. Track safety gear expiry. |
| CrewMaintenance | Never miss a service interval. | Trucks stay running. No surprise breakdowns. |
| CrewSchedule | Everyone knows where to be. | Crews stop calling asking where to go. |
| CrewGroup | Know if every job made money. | Real job costing, not gut feeling. |

> Pricing is TBD. The priority is getting a working model that R&R Florida trusts and uses daily. Revenue conversations come after that proof point exists.

---

## First Client — R&R Florida

Roofing & Renovations of Florida LLC is Client #1 and the real-world test bed for everything. If it doesn't work for them, it doesn't ship to anyone else.

| Name | Role | Uses |
|---|---|---|
| Doug | Owner | High-level dashboard, profitability visibility |
| Robert | Project Manager | Full platform — building and running it |
| Richard / Jake / Eric / Zach | Management | Dashboard, review queue, scheduling |
| Kim | Accountant | Ledger, reports, QuickBooks export |
| 10-15 Field Employees | Cardholders | SMS receipt submission only |

---

## Build Guardrails — Always

- **Finish one module before starting the next.** Partial systems create debt.
- **Real world use is the only proof.** Code that isn't being used by Kim and the crew is not done.
- **The employee database is sacred.** Every module depends on it. Changes require review.
- **Mobile first on every UI decision.** Field crews live on their phones.
- **Keep it familiar.** Tools should feel like tools people already know.
- **Specs before code.** Use OpenSpec. No vague prompts, no surprises.
- **One feature at a time.** Deploy and verify before the next one starts.
- **The platform is only as good as the data going into it.** OCR quality matters.

---

*CrewOS Full System Roadmap | Feb 2026 | Robert Cordero | Tech Quest LLC | Living Document — Update As Things Change*
