"""CEAT's approved wording, read out of the skill's reference files at runtime.

Before this module existed, draft.py carried its own hard-coded copy of every
paragraph, and that copy had already drifted from the skill (shortened consumer
blocks, a dropped sentence, a missing "kindly note"). Now each fixed paragraph
is looked up in the reference file by its opening words, its {{SLOTS}} are
filled, and only if the paragraph cannot be found does the code fall back to
its built-in copy — and that fallback is reported as template drift, so an edit
to the skill can never be silently ignored.
"""
from __future__ import annotations
import re
from functools import lru_cache

from . import skill_loader as SK

SLOT = re.compile(r"\{\{\s*([A-Z0-9_/.\-]+)\s*\}\}")


class MissingSlot(KeyError):
    """A {{SLOT}} in the approved text has no value for this case."""


# --------------------------------------------------------------------------
# normalising
# --------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def curly(s: str) -> str:
    """Straight double quotes in the reference files -> the curly quotes the
    notices have always used ("Goods" -> “Goods”)."""
    return re.sub(r'"([^"\n]*)"', r"“\1”", s)


def strip_instructions(s: str) -> str:
    """Drafting instructions written inline in the templates — '(e.g., ...)',
    '(optional — ...)' — are for the drafter, never for the notice."""
    s = re.sub(r"\s*\((?:e\.g\.|optional|see |include |single:|how the|one entry|"
               r"replacement|Invoice No\.|SR No\.)[^()]*\)", "", s)
    return s.strip()


def plural(s: str, n: int) -> str:
    """cheque(s) / was/were / it/they, resolved for the actual count."""
    many = n > 1
    s = re.sub(r"\b(\w+)\(s\)", lambda m: m.group(1) + ("s" if many else ""), s)
    for one in ("was/were", "it/they", "is/are", "has/have"):
        a, b = one.split("/")
        s = s.replace(one, b if many else a)
    return s


def fill(text: str, values: dict, n: int | None = None) -> str:
    """Fill every {{SLOT}}. A slot without a value raises MissingSlot rather than
    printing a guess or a bare marker. `n` resolves cheque(s)/was/were for a
    count; leave it None for text such as "tyre(s)/tube(s)" that must stay as is."""
    def rep(m):
        key = m.group(1)
        if key not in values or values[key] in (None, ""):
            raise MissingSlot(key)
        return str(values[key])
    out = SLOT.sub(rep, text)
    return curly(plural(out, n) if n is not None else out)


# --------------------------------------------------------------------------
# numbered templates (s138, recovery, breach, ...)
# --------------------------------------------------------------------------
@lru_cache(maxsize=None)
def paragraphs(kind: str) -> tuple[str, ...]:
    """Every paragraph of the reference file's ``Template`` code block, with its
    leading number removed and its lines joined."""
    tpl = SK.notice_ref(kind).template or ""
    out, cur = [], []
    for line in tpl.splitlines():
        if not line.strip():
            if cur:
                out.append(" ".join(cur))
                cur = []
            continue
        cur.append(line.strip())
    if cur:
        out.append(" ".join(cur))
    cleaned = []
    for p in out:
        p = re.sub(r"^\d+\.\s+", "", p)
        cleaned.append(re.sub(r"\s+", " ", p).strip())
    return tuple(cleaned)


def para(kind: str, anchor: str) -> str | None:
    """The template paragraph that opens with `anchor` (quotes and spacing
    ignored), or None if the reference file no longer has it."""
    a = _norm(anchor).lower()
    for p in paragraphs(kind):
        if _norm(p).lower().startswith(a):
            return strip_instructions(p)
    return None


def subject(kind: str) -> str | None:
    p = para(kind, "Sub:")
    return re.sub(r"^Sub:\s*", "", p).strip() if p else None


# --------------------------------------------------------------------------
# quoted blocks (clause library, consumer reply)
# --------------------------------------------------------------------------
def _quoted_after(txt: str, label_rx: str) -> str | None:
    lines = txt.splitlines()
    for i, line in enumerate(lines):
        if re.search(label_rx, line):
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith(">"):
                if lines[j].startswith("## ") or lines[j].startswith("**"):
                    break                        # the next label: no quote here
                j += 1
            block = []
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                block.append(lines[j].lstrip()[1:].strip())
                j += 1
            if not block:
                return None
            # a quote can carry a second paragraph of drafting guidance in
            # brackets — "(Use "Goods" in ...)" — which never enters a notice
            paras, cur = [], []
            for b in block + [""]:
                if b:
                    cur.append(b)
                elif cur:
                    paras.append(" ".join(cur))
                    cur = []
            keep = [p for p in paras if not p.startswith("(")]
            return re.sub(r"\s+", " ", " ".join(keep)).strip() or None
    return None


@lru_cache(maxsize=None)
def clause(heading: str) -> str | None:
    """A block from clause-library.md by its ## heading (prefix match)."""
    return _quoted_after(SK.clause_library(), r"^##\s+" + re.escape(heading))


@lru_cache(maxsize=None)
def block(kind: str, label: str) -> str | None:
    """A labelled standard block from a reference file, e.g. the consumer
    reply's '**(B) Warranty procedure:**'."""
    return _quoted_after(SK.reference(kind), re.escape(label))


# --------------------------------------------------------------------------
# drift report
# --------------------------------------------------------------------------
DRIFT: dict[str, list[str]] = {}      # kind -> paragraphs that fell back to the built-in copy


def record(kind: str, what: str) -> None:
    DRIFT.setdefault(kind, [])
    if what not in DRIFT[kind]:
        DRIFT[kind].append(what)


def drift(kind: str) -> list[str]:
    """Paragraphs the last draft of this kind had to take from the built-in copy
    because the reference file no longer contains them."""
    return list(DRIFT.get(kind, []))


def reset(kind: str) -> None:
    DRIFT[kind] = []
