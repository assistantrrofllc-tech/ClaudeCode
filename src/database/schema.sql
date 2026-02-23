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
    photo           TEXT,
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
