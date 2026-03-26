"""
database.py — 同時支援 SQLite（本機）與 PostgreSQL（Render）

- 本機開發：不設定 DATABASE_URL，自動用 SQLite (cpbl.db)
- Render 部署：設定 DATABASE_URL=postgresql://... 自動切換
"""
import os, re, sqlite3
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Render 提供的舊格式是 postgres://，psycopg2 需要 postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_PG  = DATABASE_URL.startswith("postgresql://")
DB_PATH = os.getenv("DB_PATH", "cpbl.db")


# ── SQLite 連線 ───────────────────────────────────────────────────────────

def _sqlite_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── PostgreSQL 相容層 ──────────────────────────────────────────────────────

class _PGRow:
    """讓 psycopg2 RealDictRow 支援 row['key'] 與 row.key 兩種存取"""
    def __init__(self, data: dict):
        self._data = dict(data)

    def __getitem__(self, key):
        return self._data[key]

    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError(key)

    def keys(self):
        return self._data.keys()

    def __repr__(self):
        return f"<Row {self._data}>"


def _adapt_sql(sql: str) -> str:
    """將 SQLite 語法轉換為 PostgreSQL 語法。

    所有時間欄位存的是 TEXT（格式 'YYYY-MM-DD HH24:MI:SS'），
    因此 NOW() 也要轉成相同格式的 TEXT，才能做 <= >= 比較，
    否則 PostgreSQL 會報 'operator does not exist: text <= timestamptz'。
    """
    # 佔位符 ? → %s
    sql = sql.replace("?", "%s")
    # datetime('now') → to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
    sql = sql.replace("datetime('now')", "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')")
    # date('now') → to_char(NOW(), 'YYYY-MM-DD')
    sql = sql.replace("date('now')", "to_char(NOW(), 'YYYY-MM-DD')")
    # datetime('now', 'N days') → to_char(NOW() + INTERVAL 'N days', ...)
    sql = re.sub(
        r"datetime\('now',\s*'(-?\d+)\s+days?'\)",
        lambda m: f"to_char(NOW() + INTERVAL '{m.group(1)} days', 'YYYY-MM-DD HH24:MI:SS')",
        sql
    )
    sql = re.sub(
        r"date\('now',\s*'(-?\d+)\s+days?'\)",
        lambda m: f"to_char(NOW() + INTERVAL '{m.group(1)} days', 'YYYY-MM-DD')",
        sql
    )
    return sql


class _PGWrapper:
    """包裝 psycopg2 connection，讓介面與 sqlite3 一致"""
    def __init__(self):
        import psycopg2, psycopg2.extras
        self._conn = psycopg2.connect(DATABASE_URL)
        self._cur  = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self.lastrowid = None

    def execute(self, sql, params=()):
        sql = _adapt_sql(sql)
        self._cur.execute(sql, params or ())
        # 取得 SERIAL 自增 ID
        if sql.strip().upper().startswith("INSERT"):
            try:
                self._cur.execute("SELECT lastval()")
                row = self._cur.fetchone()
                self.lastrowid = list(row.values())[0] if row else None
            except Exception:
                self.lastrowid = None
        return self

    def executescript(self, script: str):
        """相容 SQLite executescript：逐句執行"""
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if not stmt or stmt.startswith("--"):
                continue
            try:
                self.execute(stmt)
            except Exception:
                self._conn.rollback()

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return _PGRow(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [_PGRow(r) for r in rows]

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._cur.close()
        self._conn.close()


# ── Context manager（統一入口）────────────────────────────────────────────

@contextmanager
def db():
    conn = _PGWrapper() if USE_PG else _sqlite_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS members (
    discord_id TEXT PRIMARY KEY, username TEXT NOT NULL, team TEXT,
    points INTEGER DEFAULT 0, total_earned INTEGER DEFAULT 0,
    credit_score INTEGER DEFAULT 100, is_banned INTEGER DEFAULT 0,
    is_vip INTEGER DEFAULT 0, role TEXT DEFAULT 'member',
    joined_at TEXT DEFAULT (datetime('now')), last_active TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id TEXT NOT NULL,
    date TEXT NOT NULL, UNIQUE(discord_id, date)
);
CREATE TABLE IF NOT EXISTS point_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id TEXT NOT NULL,
    amount INTEGER NOT NULL, reason TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS shop_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    description TEXT, cost INTEGER NOT NULL, stock INTEGER DEFAULT -1,
    is_active INTEGER DEFAULT 1, image_url TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS shop_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id TEXT NOT NULL,
    item_id INTEGER NOT NULL, status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS bet_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
    description TEXT, options TEXT NOT NULL, odds TEXT NOT NULL,
    status TEXT DEFAULT 'open', result TEXT,
    created_at TEXT DEFAULT (datetime('now')), closes_at TEXT, settled_at TEXT
);
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
    discord_id TEXT NOT NULL, option TEXT NOT NULL,
    amount INTEGER NOT NULL, payout INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending', created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ticket_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id TEXT NOT NULL,
    game_date TEXT NOT NULL, team_home TEXT NOT NULL, team_away TEXT NOT NULL,
    seat_section TEXT NOT NULL, seat_row TEXT, seat_num TEXT,
    price INTEGER NOT NULL, quantity INTEGER DEFAULT 1,
    contact TEXT NOT NULL, status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rater_id TEXT NOT NULL,
    rated_id TEXT NOT NULL, is_positive INTEGER NOT NULL,
    comment TEXT, created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id TEXT NOT NULL,
    type TEXT NOT NULL, detail TEXT, mod_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS elections (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
    status TEXT DEFAULT 'accepting_candidates',
    starts_at TEXT, ends_at TEXT, created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT, election_id INTEGER NOT NULL,
    discord_id TEXT NOT NULL, name TEXT NOT NULL, votes INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS election_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, election_id INTEGER NOT NULL,
    voter_id TEXT NOT NULL, candidate_id INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')), UNIQUE(election_id, voter_id)
);
CREATE TABLE IF NOT EXISTS draft_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
    status TEXT DEFAULT 'setup', rounds INTEGER DEFAULT 3,
    time_per_pick INTEGER DEFAULT 180, current_pick INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS draft_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL,
    team_name TEXT NOT NULL, gm_discord_id TEXT, pick_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS draft_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL,
    name TEXT NOT NULL, position TEXT, team_origin TEXT, stats TEXT,
    drafted_by INTEGER, pick_number INTEGER
);
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT, trigger TEXT NOT NULL UNIQUE,
    response TEXT NOT NULL, is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS feed_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
    ext_id TEXT NOT NULL, pushed_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source, ext_id)
);
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL, role TEXT DEFAULT 'moderator',
    discord_id TEXT, created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id TEXT NOT NULL,
    category TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
    status TEXT DEFAULT 'open', assigned_to TEXT,
    created_at TEXT DEFAULT (datetime('now')), closed_at TEXT
);
"""

_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS members (
    discord_id TEXT PRIMARY KEY, username TEXT NOT NULL, team TEXT,
    points INTEGER DEFAULT 0, total_earned INTEGER DEFAULT 0,
    credit_score INTEGER DEFAULT 100, is_banned INTEGER DEFAULT 0,
    is_vip INTEGER DEFAULT 0, role TEXT DEFAULT 'member',
    joined_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), last_active TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS checkins (
    id SERIAL PRIMARY KEY, discord_id TEXT NOT NULL,
    date TEXT NOT NULL, UNIQUE(discord_id, date)
);
CREATE TABLE IF NOT EXISTS point_transactions (
    id SERIAL PRIMARY KEY, discord_id TEXT NOT NULL,
    amount INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS shop_items (
    id SERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT,
    cost INTEGER NOT NULL, stock INTEGER DEFAULT -1, is_active INTEGER DEFAULT 1,
    image_url TEXT, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS shop_orders (
    id SERIAL PRIMARY KEY, discord_id TEXT NOT NULL,
    item_id INTEGER NOT NULL, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS bet_events (
    id SERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT,
    options TEXT NOT NULL, odds TEXT NOT NULL, status TEXT DEFAULT 'open',
    result TEXT, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), closes_at TEXT, settled_at TEXT
);
CREATE TABLE IF NOT EXISTS bets (
    id SERIAL PRIMARY KEY, event_id INTEGER NOT NULL,
    discord_id TEXT NOT NULL, option TEXT NOT NULL,
    amount INTEGER NOT NULL, payout INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending', created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS ticket_listings (
    id SERIAL PRIMARY KEY, discord_id TEXT NOT NULL,
    game_date TEXT NOT NULL, team_home TEXT NOT NULL, team_away TEXT NOT NULL,
    seat_section TEXT NOT NULL, seat_row TEXT, seat_num TEXT,
    price INTEGER NOT NULL, quantity INTEGER DEFAULT 1,
    contact TEXT NOT NULL, status TEXT DEFAULT 'active', created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS ratings (
    id SERIAL PRIMARY KEY, rater_id TEXT NOT NULL, rated_id TEXT NOT NULL,
    is_positive INTEGER NOT NULL, comment TEXT, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS violations (
    id SERIAL PRIMARY KEY, discord_id TEXT NOT NULL, type TEXT NOT NULL,
    detail TEXT, mod_id TEXT, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS elections (
    id SERIAL PRIMARY KEY, title TEXT NOT NULL,
    status TEXT DEFAULT 'accepting_candidates',
    starts_at TEXT, ends_at TEXT, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY, election_id INTEGER NOT NULL,
    discord_id TEXT NOT NULL, name TEXT NOT NULL, votes INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS election_votes (
    id SERIAL PRIMARY KEY, election_id INTEGER NOT NULL,
    voter_id TEXT NOT NULL, candidate_id INTEGER NOT NULL,
    created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), UNIQUE(election_id, voter_id)
);
CREATE TABLE IF NOT EXISTS draft_sessions (
    id SERIAL PRIMARY KEY, title TEXT NOT NULL, status TEXT DEFAULT 'setup',
    rounds INTEGER DEFAULT 3, time_per_pick INTEGER DEFAULT 180,
    current_pick INTEGER DEFAULT 1, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS draft_teams (
    id SERIAL PRIMARY KEY, session_id INTEGER NOT NULL,
    team_name TEXT NOT NULL, gm_discord_id TEXT, pick_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS draft_players (
    id SERIAL PRIMARY KEY, session_id INTEGER NOT NULL, name TEXT NOT NULL,
    position TEXT, team_origin TEXT, stats TEXT,
    drafted_by INTEGER, pick_number INTEGER
);
CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY, trigger TEXT NOT NULL UNIQUE,
    response TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS feed_cache (
    id SERIAL PRIMARY KEY, source TEXT NOT NULL, ext_id TEXT NOT NULL,
    pushed_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), UNIQUE(source, ext_id)
);
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL, role TEXT DEFAULT 'moderator',
    discord_id TEXT, created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS support_tickets (
    id SERIAL PRIMARY KEY, discord_id TEXT NOT NULL,
    category TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
    status TEXT DEFAULT 'open', assigned_to TEXT,
    created_at TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), closed_at TEXT
);
"""


def init_db():
    if USE_PG:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        for stmt in _SCHEMA_PG.split(";"):
            stmt = stmt.strip()
            if not stmt or stmt.startswith("--"):
                continue
            try:
                cur.execute(stmt)
            except Exception as e:
                print(f"[DB] Schema warning: {e}")
                conn.rollback()
        conn.commit()
        cur.close()
        conn.close()
        print("[DB] PostgreSQL initialized")
    else:
        conn = _sqlite_conn()
        conn.executescript(_SCHEMA_SQLITE)
        conn.commit()
        conn.close()
        print("[DB] SQLite initialized")