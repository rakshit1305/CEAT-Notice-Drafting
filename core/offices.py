"""The offices a notice can be issued from — letterhead and registered office.

Until now the letterhead was a single block parsed out of house-style.md, so
every notice went out on the Mumbai registered office whatever the matter was.
CEAT issues from more than one place, and which one a notice carries is a
decision for the person drafting it, not a constant in a reference file.

So the addresses live here instead: a small editable list, seeded from
house-style.md so an existing deployment keeps the exact letterhead it has
today, and extended by the user from the page.

Storage is a JSON file beside app.py. On a hosted deployment that file lives
for as long as the container does, which covers a working session but not a
redeploy — so OFFICES_JSON can point somewhere durable, and a read-only disk
degrades to session-only rather than raising.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from . import skill_loader as SK
from .config import ROOT

STORE = Path(os.getenv("OFFICES_JSON") or (ROOT / "offices.json"))

# Set when the disk is read-only: the app still works, the list just does not
# outlive the process. app.py reads this to tell the user plainly.
LAST_SAVE_ERROR: str = ""

FIELDS = ("id", "label", "name", "address", "meta", "reg_office")


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t or "office"


def _derive_reg_office(address: str) -> str:
    """The one-line form used mid-sentence: "...Registered Office at <here>"."""
    line = " ".join(str(address or "").split())
    line = re.sub(r",?\s*India\s*$", "", line, flags=re.I)
    return line.strip(" ,")


def _clean(rec: dict) -> dict:
    out = {k: str(rec.get(k) or "").strip() for k in FIELDS}
    out["address"] = "\n".join(l.strip() for l in out["address"].splitlines() if l.strip())
    if not out["reg_office"]:
        out["reg_office"] = _derive_reg_office(out["address"])
    if not out["label"]:
        first = out["address"].splitlines()[-1] if out["address"] else out["name"]
        out["label"] = first[:48] or "Office"
    if not out["id"]:
        out["id"] = _slug(out["label"])
    return out


def seed_from_house_style() -> dict:
    """The letterhead the app has always used, as office number one.

    Read through skill_loader so it stays the single source of that block —
    if house-style.md changes, a fresh deployment picks the change up.
    """
    lh = SK.letterhead()
    return _clean(dict(
        id="house-style",
        label="Registered Office — Mumbai",
        name=lh.get("name") or "CEAT Limited",
        address=lh.get("address") or "",
        meta=lh.get("meta") or "",
        reg_office=SK.reg_office() or "",
    ))


def _blank_store() -> dict:
    first = seed_from_house_style()
    return {"default_id": first["id"], "offices": [first]}


def load() -> dict:
    """The whole store. Never raises — a damaged file falls back to the seed."""
    try:
        if STORE.exists():
            data = json.loads(STORE.read_text(encoding="utf-8"))
            offices = [_clean(o) for o in data.get("offices", []) if isinstance(o, dict)]
            offices = [o for o in offices if o["name"] or o["address"]]
            if offices:
                ids = {o["id"] for o in offices}
                default_id = data.get("default_id")
                return {"default_id": default_id if default_id in ids else offices[0]["id"],
                        "offices": offices}
    except Exception:
        pass                                  # unreadable or malformed — reseed
    return _blank_store()


def save(store: dict) -> bool:
    """Write the store. False (with LAST_SAVE_ERROR set) if the disk refuses."""
    global LAST_SAVE_ERROR
    try:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        LAST_SAVE_ERROR = ""
        return True
    except Exception as exc:
        LAST_SAVE_ERROR = f"{type(exc).__name__}: {exc}"
        return False


def all_offices(store: dict | None = None) -> list[dict]:
    return (store or load())["offices"]


def get(office_id: str, store: dict | None = None) -> dict:
    """One office by id, falling back to the default rather than to nothing."""
    st_ = store or load()
    for o in st_["offices"]:
        if o["id"] == office_id:
            return o
    for o in st_["offices"]:
        if o["id"] == st_["default_id"]:
            return o
    return st_["offices"][0] if st_["offices"] else seed_from_house_style()


def upsert(rec: dict, store: dict | None = None, make_default: bool = False) -> dict:
    """Add an office, or replace one with the same id. Ids stay unique."""
    st_ = store or load()
    rec = _clean(rec)
    existing = {o["id"] for o in st_["offices"] if o["id"] != rec.get("_was")}
    if rec["id"] in existing and rec.get("_was") != rec["id"]:
        base, n = rec["id"], 2
        while f"{base}-{n}" in existing:
            n += 1
        rec["id"] = f"{base}-{n}"
    rec.pop("_was", None)

    for i, o in enumerate(st_["offices"]):
        if o["id"] == rec["id"]:
            st_["offices"][i] = rec
            break
    else:
        st_["offices"].append(rec)

    if make_default or len(st_["offices"]) == 1:
        st_["default_id"] = rec["id"]
    save(st_)
    return st_


def remove(office_id: str, store: dict | None = None) -> dict:
    """Delete an office. The last one is never removed — a notice needs a head."""
    st_ = store or load()
    if len(st_["offices"]) <= 1:
        return st_
    st_["offices"] = [o for o in st_["offices"] if o["id"] != office_id]
    if st_["default_id"] == office_id:
        st_["default_id"] = st_["offices"][0]["id"]
    save(st_)
    return st_


def set_default(office_id: str, store: dict | None = None) -> dict:
    st_ = store or load()
    if any(o["id"] == office_id for o in st_["offices"]):
        st_["default_id"] = office_id
        save(st_)
    return st_


def for_case(case: dict) -> dict:
    """The office this notice carries.

    draft.py calls this, so the choice travels with the case rather than through
    module state — the preview, the .docx and the body text cannot drift apart,
    and a notice drafted earlier still renders on the head it was drafted on.
    """
    if isinstance(case, dict):
        inline = case.get("_office")
        if isinstance(inline, dict) and (inline.get("name") or inline.get("address")):
            return _clean(inline)
        if isinstance(inline, str) and inline.strip():
            return get(inline.strip())
    return get("")
