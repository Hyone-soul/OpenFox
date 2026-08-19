PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS phone_numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    number TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE (company_id, number)
);

CREATE TABLE IF NOT EXISTS call_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    phone_number_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'outbound'
        CHECK (direction IN ('inbound', 'outbound')),
    duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
    status TEXT NOT NULL DEFAULT 'completed'
        CHECK (status IN ('completed', 'missed', 'cancelled', 'failed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (phone_number_id) REFERENCES phone_numbers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_phone_numbers_company
    ON phone_numbers(company_id);

CREATE INDEX IF NOT EXISTS idx_call_records_company_date
    ON call_records(company_id, started_at, status);

CREATE INDEX IF NOT EXISTS idx_call_records_phone_date
    ON call_records(phone_number_id, started_at, status);
