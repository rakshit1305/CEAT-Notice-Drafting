"""Postgres, when DATABASE_URL is set. Nothing here runs otherwise.

One connection for the process, behind a lock: a drafting console has a handful
of people on it, and every statement is a few milliseconds. The first use
creates the database if the server does not have it yet and applies
db/schema.sql followed by db/migrations/*.sql in name order — all of it is
idempotent, so starting the app is the whole install.
"""
from __future__ import annotations

import contextlib
import contextvars
import json
import math
import threading

from .config import DATABASE_URL, ROOT

SCHEMA = ROOT / "db" / "schema.sql"
MIGRATIONS = ROOT / "db" / "migrations"

_lock = threading.RLock()
_conn = None
_schema_applied = False

# Who the current script run is working for, so a model call made deep inside
# analyse.py can be put against a person and a matter without threading both
# through every signature.
_actor: contextvars.ContextVar[dict] = contextvars.ContextVar("actor", default={})


def enabled() -> bool:
    return bool(DATABASE_URL)


# ---------------------------------------------------------------- values ---
def clean(obj):
    """Make a value storable: Postgres takes neither NUL bytes nor NaN."""
    if isinstance(obj, str):
        return obj.replace("\x00", "")
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean(v) for v in obj]
    if obj is None or isinstance(obj, (bool, int)):
        return obj
    return str(obj).replace("\x00", "")       # dates, Decimals, numpy scalars


def jdump(obj) -> str:
    """JSON text for a ::jsonb parameter. Sorted, so the same case always dumps
    to the same string and can be compared to tell whether it needs saving."""
    return json.dumps(clean(obj), ensure_ascii=False, sort_keys=True)


# ------------------------------------------------------------ connection ---
def _open(url: str):
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=8)


def _create_database() -> None:
    """The server is there but the database is not: make it."""
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    info = conninfo_to_dict(DATABASE_URL)
    name = info.get("dbname") or info.get("user") or "ceat_notices"
    admin = make_conninfo(**{**info, "dbname": "postgres"})
    with psycopg.connect(admin, autocommit=True, connect_timeout=8) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def _apply_schema(c) -> None:
    files = [SCHEMA] + (sorted(MIGRATIONS.glob("*.sql")) if MIGRATIONS.is_dir() else [])
    for f in files:
        c.execute(f.read_text(encoding="utf-8"))


def conn():
    """The live connection, opened (and the schema applied) on first use."""
    global _conn, _schema_applied
    import psycopg
    with _lock:
        if _conn is not None and not _conn.closed:
            return _conn
        try:
            _conn = _open(DATABASE_URL)
        except psycopg.OperationalError as e:
            if "does not exist" not in str(e) or "database" not in str(e):
                raise
            _create_database()
            _conn = _open(DATABASE_URL)
        if not _schema_applied:
            _apply_schema(_conn)
            _schema_applied = True
        return _conn


def _drop() -> None:
    global _conn
    with contextlib.suppress(Exception):
        if _conn is not None:
            _conn.close()
    _conn = None


def init() -> str:
    """Connect and make sure the tables exist. Returns "" or what went wrong."""
    if not enabled():
        return ""
    try:
        conn()
        return ""
    except Exception as e:                       # shown on the sign-in page
        _drop()
        return f"{type(e).__name__}: {e}".strip()[:400]


def q(sql_text: str, params=None) -> list[dict]:
    """Run one statement; rows as dicts ([] when it returns none). A connection
    the server dropped while idle is reopened once."""
    import psycopg
    with _lock:
        for attempt in (0, 1):
            try:
                cur = conn().execute(sql_text, params)
                return cur.fetchall() if cur.description else []
            except (psycopg.OperationalError, psycopg.InterfaceError):
                _drop()
                if attempt:
                    raise
    return []


def one(sql_text: str, params=None) -> dict | None:
    rows = q(sql_text, params)
    return rows[0] if rows else None


@contextlib.contextmanager
def tx():
    """Several statements, all or nothing. Use q()/one() inside it."""
    with _lock:
        with conn().transaction():
            yield


# ----------------------------------------------------------------- actor ---
def set_actor(user_id=None, email=None, matter_id=None) -> None:
    _actor.set(dict(user_id=user_id, email=email, matter_id=matter_id))


def log_llm(model: str, provider: str, purpose: str, tokens_in=None, tokens_out=None,
            latency_ms=None, meta: dict | None = None) -> None:
    """Record one model call. Never raises: a logging failure must not cost the
    user the answer the model just gave."""
    if not enabled():
        return
    a = _actor.get() or {}
    try:
        q("INSERT INTO llm_calls (model, provider, purpose, tokens_in, tokens_out, latency_ms,"
          " meta, matter_id, user_id, user_email)"
          " VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb,"
          " (SELECT id FROM matters WHERE id = %s), (SELECT id FROM app_users WHERE id = %s), %s)",
          (str(model), provider, purpose, tokens_in, tokens_out, latency_ms, jdump(meta or {}),
           a.get("matter_id"), a.get("user_id"), a.get("email")))
    except Exception:
        pass
