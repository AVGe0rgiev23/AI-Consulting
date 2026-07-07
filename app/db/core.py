import sqlite3
import threading
from pathlib import Path

from app import config

_local = threading.local()
_SCHEMA = Path(__file__).with_name("schema.sql")


def _connect(path):
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect(config.DB_PATH)
        _local.conn = conn
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    _migrate(conn)
    conn.commit()


def _migrate(conn):
    _ensure_column(conn, "research_briefs", "quality", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "research_briefs", "thin_reason", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "leads", "status_reason", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "findings", "published_at", "TEXT NOT NULL DEFAULT ''")


def _ensure_column(conn, table, column, decl):
    existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def reset_for_tests(path):
    config.DB_PATH = path
    _local.conn = _connect(path)
    _local.conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    _local.conn.commit()


def query_all(sql, params=()):
    return [dict(r) for r in get_conn().execute(sql, params).fetchall()]


def query_one(sql, params=()):
    row = get_conn().execute(sql, params).fetchone()
    return dict(row) if row else None


def execute(sql, params=()):
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.lastrowid


def executemany(sql, seq):
    conn = get_conn()
    conn.executemany(sql, seq)
    conn.commit()
