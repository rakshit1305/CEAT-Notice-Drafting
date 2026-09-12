"""Reads the CEAT skill as the single source of truth.

Nothing here restates a rule or a template — every string comes out of
skill/SKILL.md and skill/references/*.md. Edit the skill, the app changes.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .config import SKILL_DIR, REFERENCES

# notice type -> the reference file the skill routes it to
REF_FILE = {
    "s138":        "section-138-notice.md",
    "recovery":    "recovery-notice.md",
    "consumer":    "consumer-notice-reply.md",
    "breach":      "breach-notice.md",
    "renewal":     "renewal-notice.md",
    "termination": "termination-notice.md",
    "fm":          "force-majeure-notice.md",
    "price":       "price-adjustment-notice.md",
}
APPROVED = {"s138", "recovery", "consumer"}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


@lru_cache(maxsize=1)
def skill_md() -> str:
    return _read(SKILL_DIR / "SKILL.md")


@lru_cache(maxsize=1)
def house_style() -> str:
    return _read(REFERENCES / "house-style.md")


@lru_cache(maxsize=1)
def clause_library() -> str:
    return _read(REFERENCES / "clause-library.md")


@lru_cache(maxsize=1)
def legal_sources() -> str:
    return _read(REFERENCES / "legal-sources.md")


@lru_cache(maxsize=None)
def reference(kind: str) -> str:
    fn = REF_FILE.get(kind)
    return _read(REFERENCES / fn) if fn else ""


# --------------------------------------------------------------------------
# the ten golden rules, lifted out of SKILL.md rather than retyped
# --------------------------------------------------------------------------
@dataclass
class Rule:
    n: int
    title: str
    body: str


@lru_cache(maxsize=1)
def golden_rules() -> list[Rule]:
    txt = skill_md()
    m = re.search(r"## Golden rules.*?\n(.*?)\n## Step 1", txt, re.S)
    if not m:
        return []
    block = m.group(1)
    out: list[Rule] = []
    for chunk in re.split(r"\n(?=\d+\.\s+\*\*)", block):
        c = chunk.strip()
        hit = re.match(r"(\d+)\.\s+\*\*(.+?)\*\*(.*)", c, re.S)
        if not hit:
            continue
        body = re.sub(r"\s+", " ", hit.group(3)).strip()
        body = re.sub(r"\[(?:NEW|UPDATED)[^\]]*\]\s*", "", body)
        out.append(Rule(int(hit.group(1)), hit.group(2).strip().rstrip(".") , body))
    return out


@lru_cache(maxsize=1)
def review_banner() -> str:
    txt = skill_md()
    m = re.search(r">\s*\*\*DRAFT — for legal review before issue\.\*\*(.*?)(?:\n\n|\nThe rule)", txt, re.S)
    if not m:
        return ("DRAFT — for legal review before issue. Generated from CEAT's approved template. "
                "A qualified lawyer must verify all facts, figures, statutory references, and timelines "
                "before this notice is sent.")
    tail = re.sub(r"\n>\s*", " ", m.group(1))
    return "DRAFT — for legal review before issue." + re.sub(r"\s+", " ", tail).rstrip()


@lru_cache(maxsize=1)
def letterhead() -> dict:
    """The letterhead block, read verbatim out of house-style.md."""
    txt = house_style()
    m = re.search(r"```\s*\n(CEAT Limited.*?)\n```", txt, re.S)
    if not m:
        return dict(name="CEAT Limited", address="", meta="")
    lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
    name = lines[0]
    meta = next((l for l in lines if "CIN" in l), "")
    www = next((l for l in lines if l.lower().startswith("www")), "")
    addr = [l for l in lines[1:] if l not in (meta, www)]
    return dict(name=name,
                address="\n".join(addr),
                meta=(meta + ("   |   " + www if www else "")).strip())


@lru_cache(maxsize=1)
def reg_office() -> str:
    flat = re.sub(r"\s+", " ", reference("s138") or skill_md())
    m = re.search(r"Registered Office at (.+?)(?:, serve upon|,? (?:is|having)\b| \(|$)", flat)
    if m:
        return m.group(1).strip().rstrip(",")
    return "463, Dr. Annie Besant Road, Worli, Mumbai – 400030"


@lru_cache(maxsize=1)
def signatory_default() -> tuple[str, str]:
    m = re.search(r"_{5,}\s*\n([^\n]+)\n([^\n]+)", house_style())
    return (m.group(1).strip(), m.group(2).strip()) if m else ("", "")


# --------------------------------------------------------------------------
# per-type material handed to the model and to the validator
# --------------------------------------------------------------------------
@dataclass
class NoticeRef:
    kind: str
    approved: bool
    when_to_use: str = ""
    required_inputs: list[str] = field(default_factory=list)
    template: str = ""
    checklist: list[str] = field(default_factory=list)
    raw: str = ""


@lru_cache(maxsize=None)
def notice_ref(kind: str) -> NoticeRef:
    raw = reference(kind)
    ref = NoticeRef(kind=kind, approved=kind in APPROVED, raw=raw)
    if not raw:
        return ref

    def section(title: str) -> str:
        m = re.search(rf"##\s+{title}[^\n]*\n(.*?)(?=\n##\s|\Z)", raw, re.S | re.I)
        return m.group(1).strip() if m else ""

    ref.when_to_use = re.sub(r"\s+", " ", section("When to use")).strip()

    inputs = section("Required inputs")
    ref.required_inputs = [re.sub(r"\s+", " ", l.lstrip("-* ").strip())
                           for l in inputs.splitlines() if l.strip().startswith(("-", "*"))]

    tpl = section("Template")
    m = re.search(r"```\s*\n(.*?)\n```", tpl, re.S)
    ref.template = m.group(1) if m else tpl

    # NOTE: the three approved notice types (s138, recovery, consumer) title
    # this section "Mandatory validation checklist", while the non-standard
    # types title it "Mandatory checklist". Both must be tried, or the
    # approved types silently return an empty checklist.
    chk = (section("Mandatory validation checklist")
           or section("Mandatory checklist")
           or section("Checklist"))
    ref.checklist = [re.sub(r"\s+", " ", l.lstrip("-*[ ]x ").strip())
                     for l in chk.splitlines() if l.strip().startswith(("-", "*"))]
    return ref


def nonstandard_warning() -> str:
    m = re.search(r'\*\*"?NON-STANDARD[^"]*"?\*\*', skill_md())
    return ("NON-STANDARD — for legal review. No CEAT sample exists for this notice type; "
            "the wording follows standard legal structure in CEAT house style and must be "
            "validated by CEAT's legal team before use.")
