"""
database.py — SQLite schema & helpers
"""
import sqlite3, os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "cpbl.db")


def get_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


@contextmanager
def db():
    c = get_conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    discord_id    TEXT PRIMARY KEY,
    username      TEXT NOT NULL,
    team          TEXT,
    points        INTEGER DEFAULT 0,
    total_earned  INTEGER DEFAULT 0,
    credit_score  INTEGER DEFAULT 100,
    is_banned     INTEGER DEFAULT 0,
    is_vip        INTEGER DEFAULT 0,
    role          TEXT DEFAULT 'member',
    joined_at     TEXT DEFAULT (datetime('now')),
    last_active   TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS checkins (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  TEXT NOT NULL,
    date        TEXT NOT NULL,
    UNIQUE(discord_id, date),
    FOREIGN KEY(discord_id) REFERENCES members(discord_id)
);
CREATE TABLE IF NOT EXISTS point_transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS shop_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    cost        INTEGER NOT NULL,
    stock       INTEGER DEFAULT -1,
    is_active   INTEGER DEFAULT 1,
    image_url   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS shop_orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  TEXT NOT NULL,
    item_id     INTEGER NOT NULL,
    status      TEXT DEFAULT 'pending',
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(discord_id) REFERENCES members(discord_id),
    FOREIGN KEY(item_id)    REFERENCES shop_items(id)
);
CREATE TABLE IF NOT EXISTS bet_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    options     TEXT NOT NULL,
    odds        TEXT NOT NULL,
    status      TEXT DEFAULT 'open',
    result      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    closes_at   TEXT,
    settled_at  TEXT
);
CREATE TABLE IF NOT EXISTS bets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    INTEGER NOT NULL,
    discord_id  TEXT NOT NULL,
    option      TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    payout      INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'pending',
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(event_id)   REFERENCES bet_events(id),
    FOREIGN KEY(discord_id) REFERENCES members(discord_id)
);
CREATE TABLE IF NOT EXISTS ticket_listings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id   TEXT NOT NULL,
    game_date    TEXT NOT NULL,
    team_home    TEXT NOT NULL,
    team_away    TEXT NOT NULL,
    seat_section TEXT NOT NULL,
    seat_row     TEXT,
    seat_num     TEXT,
    price        INTEGER NOT NULL,
    quantity     INTEGER DEFAULT 1,
    contact      TEXT NOT NULL,
    status       TEXT DEFAULT 'active',
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(discord_id) REFERENCES members(discord_id)
);
CREATE TABLE IF NOT EXISTS ratings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_id    TEXT NOT NULL,
    rated_id    TEXT NOT NULL,
    is_positive INTEGER NOT NULL,
    comment     TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS violations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  TEXT NOT NULL,
    type        TEXT NOT NULL,
    detail      TEXT,
    mod_id      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS elections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    status     TEXT DEFAULT 'accepting_candidates',
    starts_at  TEXT,
    ends_at    TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS candidates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id INTEGER NOT NULL,
    discord_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    votes       INTEGER DEFAULT 0,
    FOREIGN KEY(election_id) REFERENCES elections(id)
);
CREATE TABLE IF NOT EXISTS election_votes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id  INTEGER NOT NULL,
    voter_id     TEXT NOT NULL,
    candidate_id INTEGER NOT NULL,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(election_id, voter_id)
);
CREATE TABLE IF NOT EXISTS draft_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    status          TEXT DEFAULT 'setup',
    rounds          INTEGER DEFAULT 3,
    time_per_pick   INTEGER DEFAULT 180,
    current_pick    INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS draft_teams (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL,
    team_name     TEXT NOT NULL,
    gm_discord_id TEXT,
    pick_order    INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES draft_sessions(id)
);
CREATE TABLE IF NOT EXISTS draft_players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL,
    name        TEXT NOT NULL,
    position    TEXT,
    team_origin TEXT,
    stats       TEXT,
    drafted_by  INTEGER,
    pick_number INTEGER,
    FOREIGN KEY(session_id) REFERENCES draft_sessions(id),
    FOREIGN KEY(drafted_by) REFERENCES draft_teams(id)
);
CREATE TABLE IF NOT EXISTS keywords (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger    TEXT NOT NULL UNIQUE,
    response   TEXT NOT NULL,
    is_active  INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS feed_cache (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    ext_id     TEXT NOT NULL,
    pushed_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(source, ext_id)
);
CREATE TABLE IF NOT EXISTS admins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT DEFAULT 'moderator',
    discord_id    TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS support_tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  TEXT NOT NULL,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'open',
    assigned_to TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    closed_at   TEXT
);
"""


def init_db():
    with db() as c:
        c.executescript(SCHEMA)
    print("[DB] Initialized")
