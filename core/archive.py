"""Saved notices: every drafted notice kept on disk, with a register.

    drafts/                              (or NOTICE_SAVE_DIR)
      register.csv                       one row per saved notice — opens in Excel
      2026/09/
        CEAT_Section138_Notice_<party>_20260620.docx
        CEAT_Section138_Notice_<party>_20260620.txt
        CEAT_Section138_Notice_<party>_20260620.json   the case behind it (to reopen)

Rules that follow from the skill:
- A notice with any [● …] left is saved only as a marked FILL-IN SPECIMEN
  (the .docx carries the red NOT READY TO ISSUE header), never as a clean file.
- Nothing is overwritten. A changed notice for the same party and date is
  saved as _v2, _v3 …; an identical notice is not saved twice.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

from . import compose as C
from . import draft as DRAFT
from .config import SAVE_DIR
from .schema import TYPES
from .words import fmt_amount, fmt_date, to_float

REGISTER = "register.csv"
FIELDS = ["id", "saved_at", "notice_type", "party", "subject", "notice_date", "amount",
          "status", "blanks", "review_notes", "file", "folder", "text_sha"]
READY = "Ready to issue"
SPECIMEN = "Fill-in specimen (has blanks)"


def _root(root=None) -> Path:
    r = Path(root) if root else SAVE_DIR
    r.mkdir(parents=True, exist_ok=True)
    return r


def _party(kind: str, case: dict) -> str:
    v = case.get("client_name") if kind == "consumer" else case.get("noticee_name")
    return str(v or "unnamed party").strip()


def entries(root=None) -> list[dict]:
    """Every saved notice, newest first. A file deleted from the folder by hand
    is still listed, marked missing, so the register never silently shrinks."""
    reg = _root(root) / REGISTER
    if not reg.exists():
        return []
    with reg.open(encoding="utf-8-sig", newline="") as fh:
        rows = [dict(r) for r in csv.DictReader(fh)]
    base = _root(root)
    for r in rows:
        r["missing"] = not (base / r.get("folder", "") / f"{r.get('file', '')}.docx").exists()
    return sorted(rows, key=lambda r: r.get("saved_at", ""), reverse=True)


def save(kind: str, case: dict, review_notes: int = 0, root=None, when=None) -> dict:
    """Save the notice as it would print now. Returns the register row, with
    'duplicate': True if this exact text was already saved."""
    base = _root(root)
    text = DRAFT.to_text(kind, case)
    sha = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    for e in entries(base):
        if e.get("text_sha") == sha and not e.get("missing"):
            return dict(e, duplicate=True)

    holes = C.blanks(text)
    specimen = bool(holes)
    when = when or dt.datetime.now()
    folder_rel = f"{when:%Y}/{when:%m}"
    folder = base / folder_rel
    folder.mkdir(parents=True, exist_ok=True)

    stem0 = DRAFT.filename(kind, case, specimen)[:-len(".docx")]
    stem, v = stem0, 2
    while (folder / f"{stem}.docx").exists():
        stem, v = f"{stem0}_v{v}", v + 1

    (folder / f"{stem}.docx").write_bytes(DRAFT.to_docx(kind, case, specimen=specimen))
    (folder / f"{stem}.txt").write_text(
        ("FILL-IN SPECIMEN — NOT READY TO ISSUE\n\n" if specimen else "") + text, encoding="utf-8")
    (folder / f"{stem}.json").write_text(
        json.dumps(dict(kind=kind, saved_at=when.isoformat(timespec="seconds"), case=case),
                   indent=1, ensure_ascii=False, default=str), encoding="utf-8")

    amt = to_float(case.get("amount")) if kind in ("s138", "recovery") else None
    date_key = "reply_date" if kind == "consumer" else "notice_date"
    row = dict(
        id=f"{when:%Y%m%d-%H%M%S}-{sha[:6]}",
        saved_at=when.isoformat(timespec="seconds"),
        notice_type=TYPES.get(kind, {}).get("name", kind),
        party=_party(kind, case),
        subject=DRAFT.build(kind, case)[0],
        notice_date=fmt_date(case.get(date_key)),
        amount=(fmt_amount(amt) if amt else ""),
        status=SPECIMEN if specimen else READY,
        blanks=str(len(holes)),
        review_notes=str(review_notes),
        file=stem,
        folder=folder_rel,
        text_sha=sha,
    )
    reg = base / REGISTER
    new = not reg.exists()
    with reg.open("a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    return dict(row, duplicate=False, missing=False)


def path_of(entry: dict, ext: str = "docx", root=None) -> Path:
    return _root(root) / entry.get("folder", "") / f"{entry.get('file', '')}.{ext}"


def file_bytes(entry: dict, ext: str = "docx", root=None) -> bytes | None:
    p = path_of(entry, ext, root)
    return p.read_bytes() if p.exists() else None


def load_case(entry: dict, root=None) -> tuple[str, dict] | None:
    """(kind, case) exactly as it was when the notice was saved — to reopen it."""
    p = path_of(entry, "json", root)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("kind"), data.get("case") or {}


def register_xlsx(rows: list[dict]) -> bytes:
    """The register as an Excel sheet."""
    import pandas as pd
    cols = {"saved_at": "Saved on", "notice_type": "Notice type", "party": "Party",
            "notice_date": "Notice / reply date", "amount": "Amount (INR)", "status": "Status",
            "blanks": "Blanks", "review_notes": "Review notes", "subject": "Subject",
            "folder": "Folder", "file": "File name"}
    df = pd.DataFrame([{v: r.get(k, "") for k, v in cols.items()} for r in rows], columns=list(cols.values()))
    df["Saved on"] = df["Saved on"].str.replace("T", " ", regex=False)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="Saved notices")
        ws = xw.sheets["Saved notices"]
        for i, col in enumerate(df.columns, 1):
            width = min(60, max(12, int(df[col].astype(str).str.len().max() or 0) + 2, len(col) + 2))
            ws.column_dimensions[ws.cell(1, i).column_letter].width = width
        ws.freeze_panes = "A2"
    return buf.getvalue()


def zip_of(rows: list[dict], root=None) -> bytes:
    """The chosen notices (.docx and .txt) plus the register, in one .zip."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for r in rows:
            for ext in ("docx", "txt"):
                b = file_bytes(r, ext, root)
                if b is not None:
                    z.writestr(f"{r['folder']}/{r['file']}.{ext}", b)
        z.writestr("register.xlsx", register_xlsx(rows))
    return buf.getvalue()
