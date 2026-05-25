import sqlite3
import os
import hashlib
import secrets

DB_PATH = os.path.join(os.path.dirname(__file__), "scheduler.db")


def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def _check_password(stored, password):
    salt = stored.split("$")[0]
    return _hash_password(password, salt) == stored


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS work_centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('production', 'inspection')),
            hours_per_day REAL NOT NULL DEFAULT 8,
            efficiency REAL NOT NULL DEFAULT 0.85,
            max_concurrent_jobs INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            part_number TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 5,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'unscheduled'
                CHECK(status IN ('unscheduled','scheduled','released','in_progress','completed','cancelled')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS routing_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            step_order INTEGER NOT NULL,
            work_center_id INTEGER NOT NULL REFERENCES work_centers(id),
            setup_hrs REAL NOT NULL DEFAULT 0,
            run_hrs_per_unit REAL NOT NULL DEFAULT 0,
            description TEXT,
            UNIQUE(job_id, step_order)
        );

        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            routing_step_id INTEGER NOT NULL REFERENCES routing_steps(id),
            work_center_id INTEGER NOT NULL REFERENCES work_centers(id),
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            UNIQUE(routing_step_id)
        );

        CREATE TABLE IF NOT EXISTS holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            date TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS schedule_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            data TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS license (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL UNIQUE REFERENCES tenants(id),
            hw_id TEXT NOT NULL DEFAULT '',
            trial_start TEXT,
            last_run TEXT,
            license_key TEXT DEFAULT '',
            activated_at TEXT,
            expires_at TEXT
        );
    """)
    existing = conn.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()
    if existing["c"] == 0:
        conn.execute("INSERT INTO tenants (name) VALUES (?)", ("Podrazumevani",))
        conn.execute("INSERT INTO users (username, password_hash, tenant_id) VALUES (?, ?, ?)",
                     ("admin", _hash_password("admin"), 1))
        conn.execute("INSERT INTO license (tenant_id) VALUES (?)", (1,))
        conn.commit()
    conn.close()


def register_user(username, password, tenant_name=None):
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return None, "Korisničko ime već postoji"

    if tenant_name is None:
        tenant_name = f"{username} — radni prostor"

    cur = conn.execute("INSERT INTO tenants (name) VALUES (?)", (tenant_name,))
    tenant_id = cur.lastrowid
    conn.execute("INSERT INTO users (username, password_hash, tenant_id) VALUES (?, ?, ?)",
                 (username, _hash_password(password), tenant_id))
    conn.execute("INSERT INTO license (tenant_id) VALUES (?)", (tenant_id,))
    conn.commit()

    user = conn.execute("SELECT u.*, t.name AS tenant_name FROM users u JOIN tenants t ON u.tenant_id = t.id WHERE u.id = ?",
                        (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(user), None


def authenticate_user(username, password):
    conn = get_db()
    user = conn.execute("""
        SELECT u.*, t.name AS tenant_name
        FROM users u
        JOIN tenants t ON u.tenant_id = t.id
        WHERE u.username = ?
    """, (username,)).fetchone()
    conn.close()
    if not user:
        return None, "Neispravno korisničko ime ili lozinka"
    if not _check_password(user["password_hash"], password):
        return None, "Neispravno korisničko ime ili lozinka"
    return dict(user), None
