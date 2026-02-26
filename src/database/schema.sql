-- CrewLedger Database Schema
-- Phase 1: The Ledger (Receipt Tracker)
-- Tables: employees, projects, receipts, line_items, categories, conversation_state

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================
-- EMPLOYEES
-- Phone number is the unique identifier. Auto-registered on
-- first text. No signup form, no passwords.
-- ============================================================
CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_uuid   TEXT    UNIQUE DEFAULT (lower(hex(randomblob(16)))),
    phone_number    TEXT    UNIQUE NOT NULL,
    first_name      TEXT    NOT NULL,
    full_name       TEXT,
    role            TEXT,
    crew            TEXT,
    email           TEXT,
    photo           TEXT,
    nickname        TEXT,
    is_driver       INTEGER DEFAULT 0,
    public_token    TEXT    UNIQUE,
    notes           TEXT,
    system_role     TEXT    DEFAULT 'employee'
                           CHECK(system_role IN ('super_admin', 'company_admin', 'manager', 'employee')),
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_phone ON employees(phone_number);

-- ============================================================
-- PROJECTS
-- Shared across all modules. Module 3 will extend this table.
-- Receipt tagging fuzzy-matches against project names here.
-- ============================================================
CREATE TABLE IF NOT EXISTS projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_code    TEXT    UNIQUE,
    name            TEXT    UNIQUE NOT NULL,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    status          TEXT    DEFAULT 'active' CHECK(status IN ('active', 'completed', 'on_hold')),
    start_date      TEXT,
    end_date        TEXT,
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- ============================================================
-- CATEGORIES
-- Lookup table for line item auto-categorization.
-- Seeded with defaults, refinable over time.
-- ============================================================
CREATE TABLE IF NOT EXISTS categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    UNIQUE NOT NULL,
    description     TEXT,
    is_active       INTEGER DEFAULT 1,
    sort_order      INTEGER DEFAULT 0
);

-- Seed default categories (8 per spec, sort_order = dropdown order)
INSERT OR IGNORE INTO categories (name, description, sort_order) VALUES
    ('Materials',        'Lumber, concrete, roofing materials, fasteners, adhesives', 1),
    ('Fuel',             'Gas stations, diesel, fuel for equipment',                  2),
    ('Food & Drinks',    'Crew meals, drinks, snacks on the job',                    3),
    ('Tools & Equipment','Hand tools, power tools, equipment purchases',             4),
    ('Safety Gear',      'Vests, helmets, harnesses, gloves, eyewear',               5),
    ('Office & Admin',   'Printing, office supplies, postage, permits',              6),
    ('Lodging',          'Hotels, extended stay for out of town jobs',                7),
    ('Other',            'Anything that does not fit the above',                      8);

-- ============================================================
-- RECEIPTS
-- Core table. One row per receipt submitted via SMS.
-- Status tracks the confirmation flow lifecycle.
-- ============================================================
CREATE TABLE IF NOT EXISTS receipts (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id           INTEGER NOT NULL,
    project_id            INTEGER,
    vendor_name           TEXT,
    vendor_city           TEXT,
    vendor_state          TEXT,
    purchase_date         TEXT,
    subtotal              REAL,
    tax                   REAL,
    total                 REAL,
    payment_method        TEXT,
    image_path            TEXT,
    status                TEXT    DEFAULT 'pending'
                                 CHECK(status IN ('pending', 'confirmed', 'flagged', 'rejected', 'deleted', 'duplicate')),
    flag_reason           TEXT,
    duplicate_of          INTEGER REFERENCES receipts(id),
    is_return             INTEGER DEFAULT 0,
    is_missed_receipt     INTEGER DEFAULT 0,
    matched_project_name  TEXT,
    fuzzy_match_score     REAL,
    category_id           INTEGER,
    notes                 TEXT,
    raw_ocr_json          TEXT,
    created_at            TEXT    DEFAULT (datetime('now')),
    confirmed_at          TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (project_id)  REFERENCES projects(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE INDEX IF NOT EXISTS idx_receipts_employee    ON receipts(employee_id);
CREATE INDEX IF NOT EXISTS idx_receipts_project     ON receipts(project_id);
CREATE INDEX IF NOT EXISTS idx_receipts_status      ON receipts(status);
CREATE INDEX IF NOT EXISTS idx_receipts_vendor      ON receipts(vendor_name);
CREATE INDEX IF NOT EXISTS idx_receipts_date        ON receipts(purchase_date);
CREATE INDEX IF NOT EXISTS idx_receipts_created     ON receipts(created_at);

-- ============================================================
-- LINE ITEMS
-- Individual items from a receipt. Each has its own category.
-- Unit prices stored for future cost intelligence (Phase 3).
-- ============================================================
CREATE TABLE IF NOT EXISTS line_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id      INTEGER NOT NULL,
    item_name       TEXT    NOT NULL,
    quantity        REAL    DEFAULT 1,
    unit_price      REAL,
    extended_price  REAL,
    category_id     INTEGER,
    created_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (receipt_id)  REFERENCES receipts(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE INDEX IF NOT EXISTS idx_line_items_receipt  ON line_items(receipt_id);
CREATE INDEX IF NOT EXISTS idx_line_items_category ON line_items(category_id);
CREATE INDEX IF NOT EXISTS idx_line_items_name     ON line_items(item_name);

-- ============================================================
-- CONVERSATION STATE
-- Tracks where each employee is in the SMS conversation flow.
-- One active state per employee at a time.
-- ============================================================
CREATE TABLE IF NOT EXISTS conversation_state (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL,
    receipt_id      INTEGER,
    state           TEXT    NOT NULL
                           CHECK(state IN (
                               'idle',
                               'awaiting_confirmation',
                               'awaiting_manual_entry',
                               'awaiting_missed_details'
                           )),
    context_json    TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (receipt_id)  REFERENCES receipts(id)
);

CREATE INDEX IF NOT EXISTS idx_convo_employee ON conversation_state(employee_id);
CREATE INDEX IF NOT EXISTS idx_convo_state    ON conversation_state(state);

-- ============================================================
-- UNKNOWN CONTACTS
-- Logs SMS attempts from unregistered phone numbers.
-- Displayed in dashboard review queue for management.
-- ============================================================
CREATE TABLE IF NOT EXISTS unknown_contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number    TEXT    NOT NULL,
    message_body    TEXT,
    has_media       INTEGER DEFAULT 0,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_unknown_phone ON unknown_contacts(phone_number);
CREATE INDEX IF NOT EXISTS idx_unknown_created ON unknown_contacts(created_at);

-- ============================================================
-- EMAIL SETTINGS
-- The accountant controls their own report schedule and destination.
-- Key-value store for simplicity — one row per setting.
-- ============================================================
CREATE TABLE IF NOT EXISTS email_settings (
    key             TEXT    PRIMARY KEY,
    value           TEXT    NOT NULL,
    updated_at      TEXT    DEFAULT (datetime('now'))
);

-- Seed defaults
INSERT OR IGNORE INTO email_settings (key, value) VALUES
    ('recipient_email', ''),
    ('frequency', 'weekly'),
    ('day_of_week', '1'),
    ('time_of_day', '08:00'),
    ('include_scope', 'all'),
    ('include_filter', ''),
    ('enabled', '1');

-- ============================================================
-- CERTIFICATION TYPES
-- Lookup table for certification/credential types tracked
-- per employee in the CrewCert module.
-- ============================================================
CREATE TABLE IF NOT EXISTS certification_types (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    UNIQUE NOT NULL,
    slug            TEXT    UNIQUE NOT NULL,
    sort_order      INTEGER DEFAULT 0,
    is_active       INTEGER DEFAULT 1
);

INSERT OR IGNORE INTO certification_types (name, slug, sort_order) VALUES
    ('OSHA 10',                'osha-10',           1),
    ('OSHA 30',                'osha-30',           2),
    ('First Aid / CPR',        'first-aid-cpr',     3),
    ('Fall Protection',        'fall-protection',   4),
    ('Extended Reach Forklift','ext-reach-forklift', 5),
    ('Aerial Work Platform',   'aerial-work-platform', 6),
    ('Driver',                 'driver',            7),
    ('Bilingual',              'bilingual',         8),
    ('Crew Lead',              'crew-lead',         9),
    ('Card Holder',            'card-holder',       10),
    ('Basic Rigging',          'basic-rigging',     11),
    ('Rigger/Signal Person',   'rigger-signal-person', 12);

-- ============================================================
-- CERTIFICATIONS
-- Links employees to certification types with issue/expiry dates.
-- Document path points to stored cert image/PDF.
-- ============================================================
CREATE TABLE IF NOT EXISTS certifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL,
    cert_type_id    INTEGER NOT NULL,
    issued_at       TEXT,
    expires_at      TEXT,
    document_path   TEXT,
    issuing_org     TEXT,
    notes           TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id)  REFERENCES employees(id),
    FOREIGN KEY (cert_type_id) REFERENCES certification_types(id),
    UNIQUE(employee_id, cert_type_id, issued_at)
);

CREATE INDEX IF NOT EXISTS idx_certs_employee ON certifications(employee_id);
CREATE INDEX IF NOT EXISTS idx_certs_type     ON certifications(cert_type_id);
CREATE INDEX IF NOT EXISTS idx_certs_expires  ON certifications(expires_at);

-- ============================================================
-- RECEIPT EDITS (Audit Trail)
-- Logs every field change made to a receipt after initial OCR.
-- Preserves accountability and original OCR data integrity.
-- ============================================================
CREATE TABLE IF NOT EXISTS receipt_edits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id      INTEGER NOT NULL,
    field_changed   TEXT    NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    edited_at       TEXT    DEFAULT (datetime('now')),
    edited_by       TEXT    DEFAULT 'dashboard',
    FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_receipt_edits_receipt ON receipt_edits(receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_edits_date ON receipt_edits(edited_at);

-- ============================================================
-- COMMUNICATIONS (CrewComms)
-- Cross-channel communication log: SMS, email, calls.
-- Invisible foundation — no UI triggers this table yet.
-- ============================================================
CREATE TABLE IF NOT EXISTS communications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    direction       TEXT    NOT NULL CHECK(direction IN ('inbound', 'outbound')),
    channel         TEXT    NOT NULL CHECK(channel IN ('sms', 'email', 'call')),
    from_number     TEXT,
    to_number       TEXT,
    body            TEXT,
    duration_seconds INTEGER,
    recording_url   TEXT,
    transcript      TEXT,
    project_id      INTEGER,
    contact_id      INTEGER,
    employee_id     INTEGER,
    external_id     TEXT    UNIQUE,
    imported_at     TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (project_id)  REFERENCES projects(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

CREATE INDEX IF NOT EXISTS idx_comms_direction  ON communications(direction);
CREATE INDEX IF NOT EXISTS idx_comms_channel    ON communications(channel);
CREATE INDEX IF NOT EXISTS idx_comms_from       ON communications(from_number);
CREATE INDEX IF NOT EXISTS idx_comms_to         ON communications(to_number);
CREATE INDEX IF NOT EXISTS idx_comms_employee   ON communications(employee_id);
CREATE INDEX IF NOT EXISTS idx_comms_external   ON communications(external_id);
CREATE INDEX IF NOT EXISTS idx_comms_created    ON communications(created_at);

-- ============================================================
-- USER PERMISSIONS
-- Module-level access control. Each row grants a user an access
-- level for one module. Access levels: none, view, edit, admin.
-- ============================================================
CREATE TABLE IF NOT EXISTS user_permissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    module          TEXT    NOT NULL
                           CHECK(module IN ('crewledger', 'crewcert', 'crewschedule',
                                           'crewasset', 'crewinventory', 'crewcomms', 'crewgroup')),
    access_level    TEXT    NOT NULL DEFAULT 'none'
                           CHECK(access_level IN ('none', 'view', 'edit', 'admin')),
    granted_by      INTEGER,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)    REFERENCES employees(id),
    FOREIGN KEY (granted_by) REFERENCES employees(id),
    UNIQUE(user_id, module)
);

CREATE INDEX IF NOT EXISTS idx_perms_user   ON user_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_perms_module ON user_permissions(module);

-- ============================================================
-- QR SCAN LOG
-- Logs each scan of an employee's public QR code.
-- Used for audit trail — who verified, when.
-- ============================================================
CREATE TABLE IF NOT EXISTS qr_scan_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL,
    ip_address      TEXT,
    user_agent      TEXT,
    scanned_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

CREATE INDEX IF NOT EXISTS idx_qr_scans_employee ON qr_scan_log(employee_id);
CREATE INDEX IF NOT EXISTS idx_qr_scans_time     ON qr_scan_log(scanned_at);

-- ============================================================
-- CERT ALERTS
-- Status change events for certifications. Powers dashboard
-- alerts, future notifications. Created by daily refresh job.
-- ============================================================
CREATE TABLE IF NOT EXISTS cert_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL,
    cert_id         INTEGER NOT NULL,
    alert_type      TEXT    NOT NULL
                           CHECK(alert_type IN ('expired', 'expiring', 'renewed')),
    previous_status TEXT,
    new_status      TEXT,
    days_until_expiry INTEGER,
    acknowledged    INTEGER DEFAULT 0,
    acknowledged_by TEXT,
    acknowledged_at TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (cert_id)     REFERENCES certifications(id)
);

CREATE INDEX IF NOT EXISTS idx_cert_alerts_employee ON cert_alerts(employee_id);
CREATE INDEX IF NOT EXISTS idx_cert_alerts_type     ON cert_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_cert_alerts_ack      ON cert_alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_cert_alerts_created  ON cert_alerts(created_at);

-- ============================================================
-- AUTHORIZED USERS
-- Email whitelist for Google OAuth login.
-- Only emails in this table can access the dashboard.
-- ============================================================
CREATE TABLE IF NOT EXISTS authorized_users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT    UNIQUE NOT NULL,
    name            TEXT,
    role            TEXT    DEFAULT 'viewer'
                           CHECK(role IN ('admin', 'manager', 'viewer')),
    system_role     TEXT    DEFAULT 'employee'
                           CHECK(system_role IN ('super_admin', 'company_admin', 'manager', 'employee')),
    employee_id     INTEGER REFERENCES employees(id),
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT    DEFAULT (datetime('now')),
    last_login      TEXT
);

INSERT OR IGNORE INTO authorized_users (email, name, role, system_role) VALUES
    ('official.techquest.ai@gmail.com', 'Robert Cordero', 'admin', 'super_admin');

-- ============================================================
-- VEHICLES
-- Fleet vehicles, vans, trucks, and trailers.
-- Tracks assignment, status (active/sold), and basic specs.
-- ============================================================
CREATE TABLE IF NOT EXISTS vehicles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    year            INTEGER,
    make            TEXT,
    model           TEXT,
    color           TEXT,
    tire_size       TEXT,
    plate_number    TEXT,
    vin             TEXT    UNIQUE,
    nickname        TEXT,
    assigned_to     TEXT,
    status          TEXT    DEFAULT 'active'
                           CHECK(status IN ('active', 'sold', 'out_of_service')),
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_vehicles_status ON vehicles(status);
CREATE INDEX IF NOT EXISTS idx_vehicles_vin    ON vehicles(vin);

-- ============================================================
-- VEHICLE MAINTENANCE
-- Service history for fleet vehicles. Each record captures one
-- repair/service visit with cost, mileage, and vendor.
-- ============================================================
CREATE TABLE IF NOT EXISTS vehicle_maintenance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id      INTEGER NOT NULL,
    service_date    TEXT,
    description     TEXT,
    cost            REAL,
    mileage         INTEGER,
    vendor          TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_veh_maint_vehicle ON vehicle_maintenance(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_veh_maint_date    ON vehicle_maintenance(service_date);

-- ============================================================
-- VENDORS
-- Material suppliers and vendor contacts.
-- ============================================================
CREATE TABLE IF NOT EXISTS vendors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    UNIQUE NOT NULL,
    address         TEXT,
    phone           TEXT,
    contact_name    TEXT,
    items           TEXT,
    has_account     INTEGER DEFAULT 0,
    created_at      TEXT    DEFAULT (datetime('now'))
);

-- ============================================================
-- PROJECT ASSIGNMENTS
-- Maps projects to executive, PM, and assistants.
-- ============================================================
CREATE TABLE IF NOT EXISTS project_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name    TEXT    NOT NULL,
    project_exec    TEXT,
    pm              TEXT,
    assistant_1     TEXT,
    assistant_2     TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    UNIQUE(project_name)
);

-- ============================================================
-- INVENTORY
-- Shop inventory items across locations (Orlando, Tampa).
-- ============================================================
CREATE TABLE IF NOT EXISTS inventory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name       TEXT    NOT NULL,
    quantity        TEXT,
    manufacturer    TEXT,
    location        TEXT,
    section         TEXT,
    updated_at      TEXT    DEFAULT (datetime('now')),
    created_at      TEXT    DEFAULT (datetime('now')),
    UNIQUE(item_name, location, section)
);
