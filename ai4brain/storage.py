"""SQLite persistence. Trials are the event log; snapshots are the Brain Twin's history."""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    consent_json TEXT NOT NULL,
    retention_days INTEGER NOT NULL DEFAULT 180,
    is_demo INTEGER NOT NULL DEFAULT 0,
    last_active_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_state (
    profile_id TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    grid_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    n_trials INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (profile_id, dimension)
);
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    mode TEXT NOT NULL,
    mood TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    state_json TEXT NOT NULL,
    summary_json TEXT
);
CREATE TABLE IF NOT EXISTS trial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    task TEXT NOT NULL,
    level INTEGER NOT NULL,
    item_json TEXT NOT NULL,
    response_json TEXT,
    correct INTEGER,
    y REAL,
    w REAL,
    rt_ms REAL,
    flags_json TEXT,
    confidence REAL,
    pct_before REAL,
    pct_after REAL,
    created_at TEXT NOT NULL,
    answered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_trial_profile ON trial(profile_id, dimension, answered_at);
CREATE TABLE IF NOT EXISTS snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    at TEXT NOT NULL,
    theta REAL NOT NULL,
    theta_sd REAL NOT NULL,
    pct REAL NOT NULL,
    low REAL NOT NULL,
    high REAL NOT NULL,
    n_trials INTEGER NOT NULL,
    session_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshot_profile ON snapshot(profile_id, dimension, at);
CREATE TABLE IF NOT EXISTS goal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    target_pct REAL NOT NULL,
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    start_pct REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    plan_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collab_round (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    scenario_id TEXT NOT NULL,
    events_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coach_message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    meta_json TEXT,
    at TEXT NOT NULL
);
"""

PROFILE_TABLES = [
    "coach_message", "collab_round", "plan", "goal", "snapshot", "trial", "session", "dim_state",
]


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(text):
    return datetime.fromisoformat(text)


def default_db_path():
    return os.environ.get("AI4BRAIN_DB", str(Path(__file__).resolve().parent.parent / "data" / "ai4brain.db"))


def connect(path=None):
    path = path or default_db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    return db


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def row_json(row, column, default=None):
    value = row[column]
    return json.loads(value) if value else default


def delete_profile(db, profile_id):
    """Hard delete: removes every row for the profile. Nothing identifying is kept."""
    cur = db.execute("SELECT 1 FROM profile WHERE id = ?", (profile_id,))
    if cur.fetchone() is None:
        return False
    for table in PROFILE_TABLES:
        db.execute(f"DELETE FROM {table} WHERE profile_id = ?", (profile_id,))
    db.execute("DELETE FROM profile WHERE id = ?", (profile_id,))
    db.commit()
    return True


def purge_expired(db, now=None):
    """Delete profiles inactive for longer than their chosen retention period."""
    now = now or utcnow()
    removed = 0
    for row in db.execute("SELECT id, last_active_at, retention_days FROM profile").fetchall():
        if parse_iso(row["last_active_at"]) + timedelta(days=row["retention_days"]) < now:
            if delete_profile(db, row["id"]):
                removed += 1
    return removed


def export_profile(db, profile_id):
    """Everything held about a profile, in machine-readable form."""
    out = {}
    profile = db.execute("SELECT * FROM profile WHERE id = ?", (profile_id,)).fetchone()
    if profile is None:
        return None
    out["profile"] = dict(profile)
    for table in PROFILE_TABLES:
        rows = db.execute(f"SELECT * FROM {table} WHERE profile_id = ?", (profile_id,)).fetchall()
        out[table] = [dict(r) for r in rows]
    # The full grid posteriors are bulky and derivable from the trials.
    for row in out.get("dim_state", []):
        row.pop("grid_json", None)
    return out
