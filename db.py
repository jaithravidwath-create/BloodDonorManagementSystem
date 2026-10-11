"""SQLite connection + schema."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path(os.environ.get("BDMS_DB", BASE_DIR / "data" / "bdms.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS donors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    dob           TEXT NOT NULL,
    gender        TEXT NOT NULL CHECK (gender IN ('M','F','O')),
    blood_group   TEXT NOT NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    phone         TEXT NOT NULL UNIQUE,
    email         TEXT,
    city          TEXT,
    weight_kg     REAL NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    registered_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital     TEXT NOT NULL,
    patient      TEXT NOT NULL,
    blood_group  TEXT NOT NULL,
    units        INTEGER NOT NULL CHECK (units > 0),
    units_issued INTEGER NOT NULL DEFAULT 0,
    requested_on TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','partial','fulfilled','cancelled'))
);

CREATE TABLE IF NOT EXISTS donations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id    INTEGER NOT NULL REFERENCES donors(id),
    donated_on  TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'available'
                CHECK (status IN ('available','issued','expired')),
    request_id  INTEGER REFERENCES requests(id)
);

CREATE INDEX IF NOT EXISTS idx_donations_donor  ON donations(donor_id);
CREATE INDEX IF NOT EXISTS idx_donations_status ON donations(status);
"""


def connect(path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """Open (and initialise) the database. Use ':memory:' for tests."""
    path = str(path if path is not None else DEFAULT_DB)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
