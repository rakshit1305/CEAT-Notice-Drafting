"""Matters, their attachments and the notices drafted from them, in Postgres.

    matters           one working case per person per notice type
    matter_documents  what was attached to it — the bytes and what was read out
    notices           every notice drafted, exactly as it printed

Rules carried over from the skill (and from the old drafts/ register):
- A notice with any [● …] left is stored as a specimen, and its .docx carries
  the NOT READY TO ISSUE header.
- Nothing is overwritten. A changed notice is a new row with the next version;
  an identical one is not stored twice.
"""
from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import hashlib
import mimetypes

from . import compose as C
from . import db as DB
from . import draft as DRAFT
from .extract import Doc
from .words import to_float

READY, SPECIMEN = "ready", "specimen"


def party_of(kind: str, case: dict) -> str:
    v = case.get("client_name") if kind == "consumer" else case.get("noticee_name")
    return str(v or "").strip()


# --------------------------------------------------------------- matters ---
def open_matters(user_id: int) -> dict[str, dict]:
    """notice type -> the matter this person last worked on and has not cleared."""
    rows = DB.q(
        "SELECT DISTINCT ON (notice_type) id, notice_type, case_json, status"
        "  FROM matters WHERE created_by = %s AND status <> 'closed'"
        " ORDER BY notice_type, updated_at DESC", (user_id,))
    return {r["notice_type"]: r for r in rows}


def save_matter(matter_id, kind: str, case: dict, status: str, user_id: int) -> int:
    """Insert or update; returns the matter id. A row that has gone (deleted
    behind the app's back) is simply made again."""
    args = (party_of(kind, case) or None, DB.jdump(case), status)
    if matter_id:
        row = DB.one("UPDATE matters SET party = %s, case_json = %s::jsonb, status = %s,"
                     " updated_at = now() WHERE id = %s RETURNING id", args + (matter_id,))
        if row:
            return row["id"]
    row = DB.one("INSERT INTO matters (party, case_json, status, notice_type, created_by)"
                 " VALUES (%s, %s::jsonb, %s, %s, %s) RETURNING id", args + (kind, user_id))
    return row["id"]


def close_matter(matter_id) -> None:
    if matter_id:
        DB.q("UPDATE matters SET status = 'closed', updated_at = now() WHERE id = %s",
             (matter_id,))


def matter_owner(matter_id) -> int | None:
    row = DB.one("SELECT created_by FROM matters WHERE id = %s", (matter_id,)) if matter_id else None
    return row["created_by"] if row else None


# ------------------------------------------------------------- documents ---
def save_document(matter_id: int, doc: Doc, data: bytes | None, question_key: str | None,
                  user_id: int) -> None:
    """Keep an attachment against its matter. `data` is the file as uploaded."""
    mime = doc.mime or mimetypes.guess_type(doc.name.split("  (attached to")[0])[0]
    DB.q(
        "INSERT INTO matter_documents (matter_id, question_key, file_name, file_mime, file_size,"
        " content_hash, file_bytes, doc_kind, extracted_text, extracted_tables, extraction_note,"
        " uploaded_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)"
        " ON CONFLICT (matter_id, content_hash) DO NOTHING",
        (matter_id, question_key, DB.clean(doc.name), mime, len(data) if data else None,
         hashlib.sha256(data).hexdigest() if data else doc.digest, data,
         doc.kind if doc.kind in ("text", "tables", "image", "error") else "text",
         DB.clean(doc.text or "") or None, DB.jdump(doc.tables) if doc.tables else None,
         DB.clean(doc.note or "") or None, user_id))


def load_documents(matter_id) -> dict[str, Doc]:
    """digest -> Doc, as the app holds them, rebuilt without re-parsing."""
    out: dict[str, Doc] = {}
    if not matter_id:
        return out
    for r in DB.q("SELECT file_name, file_mime, content_hash, doc_kind,"
                  " CASE WHEN doc_kind = 'image' THEN file_bytes END AS file_bytes,"
                  " extracted_text, extracted_tables, extraction_note"
                  " FROM matter_documents WHERE matter_id = %s ORDER BY id", (matter_id,)):
        d = Doc(name=r["file_name"], kind=r["doc_kind"], text=r["extracted_text"] or "",
                tables=r["extracted_tables"] or [], note=r["extraction_note"] or "",
                digest=r["content_hash"][:16])
        if d.kind == "image" and r["file_bytes"] is not None:
            d.b64 = base64.b64encode(bytes(r["file_bytes"])).decode()
            d.mime = r["file_mime"] or "image/jpeg"
        out[d.digest] = d
    return out


def delete_document(matter_id, digest: str) -> None:
    if matter_id:
        DB.q("DELETE FROM matter_documents WHERE matter_id = %s AND left(content_hash, 16) = %s",
             (matter_id, digest))


# --------------------------------------------------------------- notices ---
def _iso_date(v):
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def save_notice(matter_id, kind: str, case: dict, rep, user_id: int) -> dict:
    """Store the notice as it would print now. Returns its row, with
    'duplicate': True when this exact text is already in the register."""
    edits = case.get(f"_edits_{kind}") or {}
    text = DB.clean(DRAFT.to_text(kind, case, edits))
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    had = DB.one("SELECT id, version, status, file_name FROM notices WHERE text_sha = %s", (sha,))
    if had:
        return dict(had, duplicate=True)

    holes = C.blanks(text)
    specimen = bool(holes)
    amount = to_float(case.get("amount")) if kind in ("s138", "recovery") else None
    report = dataclasses.asdict(rep) if dataclasses.is_dataclass(rep) else None
    with DB.tx():
        ver = DB.one("SELECT COALESCE(max(version), 0) + 1 AS v FROM notices WHERE matter_id = %s",
                     (matter_id,))["v"] if matter_id else 1
        name = DRAFT.filename(kind, case, specimen)
        if ver > 1:
            name = name[:-len(".docx")] + f"_v{ver}.docx"
        row = DB.one(
            "INSERT INTO notices (matter_id, version, notice_type, party, subject, notice_date,"
            " amount, status, blanks, review_notes, file_name, body_text, text_sha, docx_bytes,"
            " case_json, report_json, saved_by)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)"
            " ON CONFLICT (text_sha) DO NOTHING RETURNING id, version, status, file_name",
            (matter_id, ver, kind, party_of(kind, case) or None,
             DB.clean(DRAFT.build(kind, case)[0]),
             _iso_date(case.get("reply_date" if kind == "consumer" else "notice_date")),
             amount or None, SPECIMEN if specimen else READY, len(holes),
             len(getattr(rep, "flags", []) or []), name, text, sha,
             DRAFT.to_docx(kind, case, edits, specimen=specimen),
             DB.jdump(case), DB.jdump(report) if report is not None else None, user_id))
    if not row:                                   # someone saved the same text this instant
        return dict(DB.one("SELECT id, version, status, file_name FROM notices"
                           " WHERE text_sha = %s", (sha,)), duplicate=True)
    return dict(row, duplicate=False)


def list_notices(limit: int = 30) -> list[dict]:
    """The register, newest first — everyone's, with who saved each."""
    return DB.q(
        "SELECT n.id, n.matter_id, n.version, n.notice_type, n.party, n.subject, n.status,"
        "       n.blanks, n.review_notes, n.file_name, n.saved_at,"
        "       u.email AS saved_by_email"
        "  FROM notices n LEFT JOIN app_users u ON u.id = n.saved_by"
        " ORDER BY n.saved_at DESC, n.id DESC LIMIT %s", (limit,))


def count_notices() -> int:
    return int(DB.one("SELECT count(*) AS n FROM notices")["n"])


def notice_case(notice_id: int) -> tuple[str, dict, int | None] | None:
    """(notice type, the case behind it, its matter) — to pick it back up."""
    r = DB.one("SELECT notice_type, case_json, matter_id FROM notices WHERE id = %s", (notice_id,))
    return (r["notice_type"], r["case_json"] or {}, r["matter_id"]) if r else None


def notice_files(notice_id: int) -> dict | None:
    """The stored notice itself: {'text', 'docx', 'file_name'}."""
    r = DB.one("SELECT body_text, docx_bytes, file_name FROM notices WHERE id = %s", (notice_id,))
    if not r:
        return None
    return dict(text=r["body_text"], file_name=r["file_name"] or "notice.docx",
                docx=bytes(r["docx_bytes"]) if r["docx_bytes"] is not None else None)


# ----------------------------------------------------------------- usage ---
def llm_usage(days: int = 30) -> list[dict]:
    return DB.q(
        "SELECT COALESCE(user_email, 'system') AS who, count(*) AS calls,"
        "       COALESCE(sum(tokens_in), 0) AS tokens_in,"
        "       COALESCE(sum(tokens_out), 0) AS tokens_out, max(created_at) AS last_call"
        "  FROM llm_calls WHERE created_at > now() - make_interval(days => %s)"
        " GROUP BY 1 ORDER BY calls DESC", (days,))
