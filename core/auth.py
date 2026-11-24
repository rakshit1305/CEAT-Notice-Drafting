"""Sign-in and accounts. Two roles — 'admin' and 'user' — and no self-signup:
an admin creates every account and hands over a temporary password, which the
person replaces the first time they sign in.

Passwords are stored as  pbkdf2_sha256$<iterations>$<b64 salt>$<b64 hash>.
A sign-in is a row in app_sessions holding only sha256(token), so reading the
database cannot be turned into a live session, and ending one — sign-out,
a password reset, a deactivation — is a DELETE that takes effect on that
person's next click.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import logging
import re
import secrets
import threading
import time

from . import db as DB
from .config import ADMIN_EMAIL, ADMIN_PASSWORD, DEFAULT_ADMIN_PASSWORD, SESSION_HOURS

log = logging.getLogger(__name__)

ITERATIONS = 600_000
MIN_PASSWORD = 8
ROLES = ("admin", "user")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COLS = ("id, email, role, is_active, must_change_password, created_at, updated_at, "
         "last_login_at")

# Wrong guesses per sign-in name, in this process. Five in a row and that name
# waits fifteen minutes — the seeded admin password is printed in the README.
_MAX_FAILS, _LOCK_SECONDS = 5, 15 * 60
_fails: dict[str, list[float]] = {}
_fails_lock = threading.Lock()
_seed_checked = False


class AuthError(ValueError):
    """Something the person can fix; the message is shown to them as it is."""


# ------------------------------------------------------------- passwords ---
def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = str(stored).split("$")
        if algo != "pbkdf2_sha256":
            return False
        want = base64.b64decode(digest)
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                  base64.b64decode(salt), int(iters))
        return hmac.compare_digest(got, want)
    except Exception:
        return False


# Verified against when the name is unknown, so "no such account" takes as long
# as "wrong password" and the sign-in page cannot be used to list accounts.
_DUMMY = hash_password(secrets.token_urlsafe(12))


def temp_password() -> str:
    return secrets.token_urlsafe(9)


def _check_new_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"A password needs at least {MIN_PASSWORD} characters.")
    if password in (ADMIN_PASSWORD, DEFAULT_ADMIN_PASSWORD):
        raise AuthError("That is the default password — choose a different one.")


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


# -------------------------------------------------------------- accounts ---
def seed_admin() -> bool:
    """Create the first admin when there are no accounts at all. Only then: an
    admin who deletes the seeded account does not get it back on restart."""
    global _seed_checked
    if _seed_checked:
        return False
    made = False
    if not DB.one("SELECT 1 AS x FROM app_users LIMIT 1"):
        made = bool(DB.q(
            "INSERT INTO app_users (email, password_hash, role, must_change_password)"
            " SELECT %s, %s, 'admin', TRUE WHERE NOT EXISTS (SELECT 1 FROM app_users)"
            " RETURNING id", (ADMIN_EMAIL, hash_password(ADMIN_PASSWORD))))
    _seed_checked = True
    if made and ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD:
        log.warning("seeded admin %s with the SHIPPED DEFAULT PASSWORD — it must be changed at "
                    "first sign-in; set ADMIN_PASSWORD before the first start on a real server",
                    ADMIN_EMAIL)
    return made


def list_users() -> list[dict]:
    return DB.q(f"SELECT {_COLS} FROM app_users ORDER BY lower(email)")


def get_user(user_id: int) -> dict | None:
    return DB.one(f"SELECT {_COLS} FROM app_users WHERE id = %s", (user_id,))


def create_user(email: str, password: str, role: str = "user") -> dict:
    email = (email or "").strip()
    if not _EMAIL.match(email):
        raise AuthError("Enter the person's email address — it is what they sign in with.")
    if role not in ROLES:
        raise AuthError("Role must be admin or user.")
    _check_new_password(password)
    if DB.one("SELECT 1 FROM app_users WHERE lower(email) = lower(%s)", (email,)):
        raise AuthError(f"{email} already has an account.")
    return DB.one(
        "INSERT INTO app_users (email, password_hash, role, must_change_password)"
        f" VALUES (%s, %s, %s, TRUE) RETURNING {_COLS}",
        (email, hash_password(password), role))


def _other_active_admins(user_id: int) -> int:
    row = DB.one("SELECT count(*) AS n FROM app_users"
                 " WHERE role = 'admin' AND is_active AND id <> %s", (user_id,))
    return int(row["n"]) if row else 0


def _guard(user_id: int, acting_id: int | None, what: str) -> dict:
    """An admin cannot lock themselves out, and the last admin cannot go."""
    u = get_user(user_id)
    if not u:
        raise AuthError("That account no longer exists.")
    if acting_id is not None and user_id == acting_id:
        raise AuthError(f"You cannot {what} your own account — ask another admin.")
    if u["role"] == "admin" and u["is_active"] and not _other_active_admins(user_id):
        raise AuthError(f"You cannot {what} the only active admin.")
    return u


def set_role(user_id: int, role: str, acting_id: int | None = None) -> None:
    if role not in ROLES:
        raise AuthError("Role must be admin or user.")
    u = get_user(user_id)
    if not u:
        raise AuthError("That account no longer exists.")
    if u["role"] == role:
        return
    if role != "admin":
        _guard(user_id, acting_id, "demote")
    DB.q("UPDATE app_users SET role = %s, updated_at = now() WHERE id = %s", (role, user_id))


def set_active(user_id: int, active: bool, acting_id: int | None = None) -> None:
    if not active:
        _guard(user_id, acting_id, "deactivate")
    DB.q("UPDATE app_users SET is_active = %s, updated_at = now() WHERE id = %s",
         (bool(active), user_id))
    if not active:
        revoke_sessions(user_id)


def reset_password(user_id: int, password: str) -> None:
    """An admin sets a temporary password; the person must replace it, and
    anywhere they are signed in is signed out."""
    _check_new_password(password)
    DB.q("UPDATE app_users SET password_hash = %s, must_change_password = TRUE,"
         " updated_at = now() WHERE id = %s", (hash_password(password), user_id))
    revoke_sessions(user_id)


def delete_user(user_id: int, acting_id: int | None = None) -> None:
    """Remove the account. Matters and notices they made stay, unattributed."""
    _guard(user_id, acting_id, "delete")
    DB.q("DELETE FROM app_users WHERE id = %s", (user_id,))


def change_password(user_id: int, new: str, current: str | None = None,
                    keep_token: str | None = None) -> None:
    """The person's own change. `current` is checked when given (it is not
    asked for straight after a sign-in that forced the change)."""
    row = DB.one("SELECT password_hash FROM app_users WHERE id = %s", (user_id,))
    if not row:
        raise AuthError("That account no longer exists.")
    if current is not None and not verify_password(current, row["password_hash"]):
        raise AuthError("The current password is not right.")
    _check_new_password(new)
    if verify_password(new, row["password_hash"]):
        raise AuthError("Choose a password different from the current one.")
    DB.q("UPDATE app_users SET password_hash = %s, must_change_password = FALSE,"
         " updated_at = now() WHERE id = %s", (hash_password(new), user_id))
    revoke_sessions(user_id, keep_token=keep_token)


# -------------------------------------------------------------- sessions ---
def _locked(name: str) -> bool:
    now = time.time()
    with _fails_lock:
        recent = [t for t in _fails.get(name, []) if now - t < _LOCK_SECONDS]
        _fails[name] = recent
        return len(recent) >= _MAX_FAILS


def _failed(name: str) -> None:
    with _fails_lock:
        _fails.setdefault(name, []).append(time.time())


def login(email: str, password: str, user_agent: str = "", ip: str = "") -> tuple[dict, str]:
    """(user, session token). Raises AuthError with one message for every way
    it can fail except the lock-out, so it gives nothing away."""
    name = (email or "").strip().lower()
    if _locked(name):
        raise AuthError("Too many wrong attempts. Try again in fifteen minutes.")
    row = DB.one(f"SELECT {_COLS}, password_hash FROM app_users WHERE lower(email) = %s", (name,))
    ok = verify_password(password or "", row["password_hash"] if row else _DUMMY)
    if not (row and ok and row["is_active"]):
        _failed(name)
        raise AuthError("That email and password do not match an active account.")
    with _fails_lock:
        _fails.pop(name, None)
    token = secrets.token_urlsafe(32)
    DB.q("DELETE FROM app_sessions WHERE expires_at < now()")
    DB.q("INSERT INTO app_sessions (token_hash, user_id, expires_at, user_agent, ip)"
         " VALUES (%s, %s, %s, %s, %s)",
         (_token_hash(token), row["id"],
          dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=SESSION_HOURS),
          (user_agent or "")[:300], (ip or "")[:64]))
    DB.q("UPDATE app_users SET last_login_at = now() WHERE id = %s", (row["id"],))
    row.pop("password_hash", None)
    return row, token


def session_user(token: str | None) -> dict | None:
    """The account behind a live session, or None once it has been signed out,
    has expired, or the account has been deactivated."""
    if not token:
        return None
    th = _token_hash(token)
    row = DB.one(
        "SELECT u.id, u.email, u.role, u.is_active, u.must_change_password,"
        "       s.last_seen_at < now() - interval '1 minute' AS stale"
        "  FROM app_sessions s JOIN app_users u ON u.id = s.user_id"
        " WHERE s.token_hash = %s AND s.expires_at > now() AND u.is_active", (th,))
    if not row:
        return None
    if row.pop("stale"):
        DB.q("UPDATE app_sessions SET last_seen_at = now() WHERE token_hash = %s", (th,))
    return row


def logout(token: str | None) -> None:
    if token:
        DB.q("DELETE FROM app_sessions WHERE token_hash = %s", (_token_hash(token),))


def revoke_sessions(user_id: int, keep_token: str | None = None) -> None:
    if keep_token:
        DB.q("DELETE FROM app_sessions WHERE user_id = %s AND token_hash <> %s",
             (user_id, _token_hash(keep_token)))
    else:
        DB.q("DELETE FROM app_sessions WHERE user_id = %s", (user_id,))
