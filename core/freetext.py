"""Read the fields out of what the user actually typed.

Several questions collect more than one field in one box — "who is it addressed
to, name and address", "how and when did it bounce". Documents are read by
analyse.deterministic and by the model; this module reads the *typed* answer,
so the console still works with no API key and no attachment.

This is reading, not inference. Nothing here supplies a fact the user did not
write; where the text does not clearly carry a field, the field stays empty and
shows as [● …] in the draft. Whatever is picked up is echoed back under the
question so it can be corrected.
"""
from __future__ import annotations
import re

from .words import find_amounts, find_dates, iso, parse_date

# ---------------------------------------------------------------- helpers --
ADDR_START = re.compile(
    r"^\s*(?:\d+[\-/A-Za-z]*\b|shop\b|plot\b|flat\b|no\.?\s*\d|h\.?\s*no\b|door\b|office\b|"
    r"unit\b|survey\b|gala\b|godown\b|building\b|bldg\b|block\b|floor\b|near\b|opp\b|"
    r"behind\b|sector\b|phase\b|khasra\b)", re.I)
# Words that introduce the person behind a firm. "partner"/"director" used to
# match only in the singular, and "owned by" / "run by" not at all — so
# "Shree Balaji Tyres, owned by Mr. Ramesh Patil" put "owned by Mr. Ramesh
# Patil" into the noticee's name.
PROP = re.compile(r"^\s*(?:(?:owned|run|managed|represented)\s+by|through\s+(?:its\s+)?"
                  r"(?:sole\s+)?(?:proprietor|proprietress|partners?|directors?)|"
                  r"prop(?:rietor|rietress|rietrix)?\.?|partners?|directors?)\b[:.,\s]*", re.I)
# "a partnership firm", "a private limited company" — a description, not a name.
DESCRIPTOR = re.compile(r"^\s*(?:a|an|the)?\s*(?:registered\s+)?(?:partnership(?:\s+firm)?|"
                        r"private\s+limited(?:\s+company)?|public\s+limited(?:\s+company)?|"
                        r"limited\s+company|company|llp|sole\s+proprietorship(?:\s+concern)?|"
                        r"proprietorship(?:\s+concern)?|proprietary\s+concern)\s*$", re.I)
PERSON = re.compile(r"\b(?:mr|mrs|ms|shri|smt|sri|dr|miss)\b\.?", re.I)
FIRMY = re.compile(r"\b(?:m/s|enterprises?|traders?|trading|agenc(?:y|ies)|industries|tyres?|"
                   r"&\s*co|and co|pvt|private|limited|ltd|llp|corporation|company|"
                   r"sons|brothers|associates|stores?|motors?)\b", re.I)
ROLE = re.compile(r"(manager|counsel|head|director|officer|secretary|advocate|partner|"
                  r"president|vice|legal|gm|dgm|agm|avp|vp)\b", re.I)


def _lines(t: str) -> list[str]:
    return [l.strip(" \t·-–—") for l in str(t or "").splitlines() if l.strip(" \t·-–—")]


def _segs(t: str) -> list[str]:
    return [s.strip() for s in re.split(r",|\n", str(t or "")) if s.strip()]


def _quoted(t: str) -> str:
    m = re.search(r"[“\"']([^”\"']{3,60})[”\"']", str(t or ""))
    return m.group(1).strip() if m else ""


def _dates_by_cue(text: str, cues: dict[str, str]) -> dict[str, str]:
    """Map each date in the text to a field, by the words just before it."""
    t = str(text or "")
    out: dict[str, str] = {}
    for m in re.finditer(r"\b(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4})\b", t):
        d = parse_date(m.group(1))
        if not d:
            continue
        lead = t[max(0, m.start() - 55):m.start()].lower()
        for field, pattern in cues.items():
            if field in out:
                continue
            if re.search(pattern, lead):
                out[field] = d.isoformat()
                break
    return out


def _after(text: str, pattern: str, stop: str = r"[.;\n]") -> str:
    m = re.search(pattern + r"\s*[:\-–—]?\s*(.+?)(?=" + stop + r"|$)", str(text or ""), re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip(" ,;") if m else ""


def _split_party(parts: list[str]) -> tuple[str, str]:
    """(addressee, proprietorship concern) — whichever part names a person is
    the addressee and whichever names a concern is the concern, regardless of
    which one carried the word "Proprietor"."""
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return (parts[0] if parts else ""), ""
    person = next((p for p in parts if PERSON.search(p)), "")
    firm = next((p for p in parts if FIRMY.search(p) and p != person), "")
    if not person and firm:                      # no honorific — whatever is not
        person = next((p for p in parts if p != firm), "")   # the concern is the person
    if person and firm:
        return person, firm
    return parts[0], ", ".join(parts[1:])


def _name_and_address(raw: str) -> tuple[str, str, str]:
    """(name, proprietorship concern, address) out of one typed block."""
    # "Shree Balaji Tyres owned by Mr. X" / "Sharma Tyres (Prop. Mr. Y)" — break
    # the person out into their own segment even without a comma.
    raw = re.sub(r"\s*\(\s*((?:prop(?:rietor|rietress)?\.?|owned by|partners?)\b[^)]*)\)", r", \1", str(raw or ""),
                 flags=re.I)
    raw = re.sub(r"(?<=[A-Za-z.])\s+(?=(?:owned|run|managed)\s+by\b)", ", ", raw, flags=re.I)
    raw = re.sub(r"(?<=[a-z])\s+(?=prop(?:rietor|rietress)?\b\.?\s)", ", ", raw, flags=re.I)
    ls = _lines(raw)
    if len(ls) >= 2:
        head, rest = ls[0], ls[1:]
        marked = ""
        if rest and PROP.match(rest[0]):
            marked = PROP.sub("", rest[0]).strip()
            rest = rest[1:]
        name, firm = _split_party([head, marked])
        return name, firm, "\n".join(rest)

    segs = _segs(raw)
    if not segs:
        return "", "", ""
    cut = next((i for i, s in enumerate(segs) if ADDR_START.match(s)), None)
    if cut is None or cut == 0:
        cut = 1 if len(segs) > 1 else len(segs)
    head_parts, tail = segs[:cut], segs[cut:]
    head_parts = [PROP.sub("", s).strip(" ()") for s in head_parts]
    head_parts = [s for s in head_parts if s and not DESCRIPTOR.match(s)]
    name, firm = _split_party(head_parts)
    return name, firm, ", ".join(tail)


def _rows_from_lines(raw: str, cols: list[str]) -> list[dict]:
    """'INV-1 | 02.05.2026 | 150000' one per line -> table rows."""
    out = []
    for line in _lines(raw):
        # A comma followed by 2–3 digits is inside an Indian-format amount
        # ("3,10,000"), not a column break — splitting there once turned a
        # ₹3,10,000 invoice into an invoice of "10".
        parts = [p.strip() for p in re.split(r"\s*\|\s*|\t+|\s{2,}|,(?!\d{2,3}\b)", line) if p.strip()]
        if len(parts) < 2:
            continue
        row = {c: "" for c in cols}
        for p in parts:
            d, a = parse_date(p), find_amounts("INR " + p)
            if d and "date" in row and not row["date"]:
                row["date"] = d.isoformat()
            elif re.fullmatch(r"[\d,]+(?:\.\d{1,2})?", p) and "amt" in row and not row["amt"]:
                row["amt"] = re.sub(r"[^\d.]", "", p)
            else:
                for c in cols:
                    if c in ("ref", "no", "sku") and not row[c]:
                        row[c] = p
                        break
        if any(row.values()):
            out.append(row)
    return out if len(out) >= 1 and any(r.get("amt") or r.get("date") for r in out) else []


# ------------------------------------------------------------------ rules --
def _parse(kind: str, qid: str, raw: str, case: dict) -> dict:
    t = str(raw or "").strip()
    if not t:
        return {}
    v: dict = {}
    low = t.lower()

    if qid == "addr":
        name, firm, addr = _name_and_address(t)
        # A company or partnership is itself the noticee (Noticee No. 1); its
        # directors/partners are read separately. Only a proprietorship splits
        # into the person (noticee) and the concern.
        multi_ = str(case.get("noticee_type", "")).startswith(("Company", "Partnership")) or \
            bool(re.search(r"\bpartnership\b|\bpvt\b|private limited|\blimited\b|\bltd\b|\bllp\b", low))
        if multi_ and firm:
            name, firm = firm, ""
        if name:
            v["noticee_name"] = name
        if firm:
            v["firm_name"] = firm
        if addr:
            v["noticee_address"] = addr

    elif qid == "chq":
        # There was no branch here at all: cheque number, date, amount and bank
        # came only from the model, so a garbled model reply had nothing to fall
        # back to and printed straight into the notice.
        chq = _cheques(t)
        if chq:
            v["cheques"] = chq
        v.update(_dates_by_cue(t, {
            "presented_date": r"present",
            "memo_date": r"memo|intimation|advice|slip",
            "dishonour_date": r"return|dishonour|dishonor|unpaid|bounce",
        }))
        reason = _quoted(t) or _after(t, r"\b(?:for the reason|reason|reasons?)\b", r"[.;\n]|vide")
        if reason:
            v["dishonour_reason"] = reason.strip(" ,;")

    elif qid == "bounce":
        v.update(_dates_by_cue(t, {
            "presented_date": r"present",
            "memo_date": r"memo|intimation|advice|slip",
            "dishonour_date": r"return|dishonour|dishonor|unpaid|bounce",
        }))
        ds = find_dates(t)
        if ds and "dishonour_date" not in v:
            v["dishonour_date"] = ds[0]
        # "returned on 28.07.2026 with bank memo of the same date"
        if "memo_date" not in v and v.get("dishonour_date") and re.search(
                r"(?:memo|intimation|advice|slip)[^.;\n]{0,30}same (?:date|day)|"
                r"same (?:date|day)[^.;\n]{0,30}(?:memo|intimation|advice|slip)", t, re.I):
            v["memo_date"] = v["dishonour_date"]
        reason = _quoted(t) or _after(t, r"\b(?:for the reason|reason|reasons?)\b", r"[.;\n]|vide")
        if reason:
            v["dishonour_reason"] = reason.strip(" ,;")

    elif qid == "amt":
        amts = find_amounts(t)
        none_paid = bool(re.search(r"\b(?:no|none|nil|not|without any)\b[^.]{0,30}"
                                   r"(?:part[- ]?pay|payment)", low))
        paid = re.search(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)[^.;\n]{0,40}?"
                         r"\b(?:received|paid|part[- ]?pa(?:id|yment))", t, re.I) or \
            re.search(r"\b(?:received|paid|part[- ]?payment of)\b[^\d.;\n]{0,20}"
                      r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)", t, re.I)
        if none_paid:
            v["part_paid"] = "0"
        elif paid:
            v["part_paid"] = re.sub(r"[^\d.]", "", paid.group(1))
            # A factual description only — this text is never printed as-is.
            v["part_payment"] = t
            d = find_dates(t)
            if d:
                v["part_paid_date"] = d[0]
        if amts:
            near = re.search(r"(?:demand(?:ed)?|balance|payable|outstanding|due|limited to)[^\d]{0,48}?"
                             r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)", t, re.I)
            if near:
                v["amount"] = re.sub(r"[^\d.]", "", near.group(1))
            elif none_paid or not paid:
                v["amount"] = str(max(amts))

    elif qid == "total":
        amts = find_amounts(t)
        if amts:
            v["amount"] = str(max(amts))
        d = _dates_by_cue(t, {"as_on_date": r"as on|as at|as of|upto|up to"})
        if d:
            v.update(d)
        elif find_dates(t):
            v["as_on_date"] = find_dates(t)[0]

    elif qid == "tax":
        p = re.search(r"principal[^\d]{0,20}([\d,]+(?:\.\d{1,2})?)", t, re.I)
        g = re.search(r"(?:gst|tax|igst|cgst)[^\d]{0,20}([\d,]+(?:\.\d{1,2})?)", t, re.I)
        if p:
            v["principal"] = re.sub(r"[^\d.]", "", p.group(1))
        if g:
            v["tax"] = re.sub(r"[^\d.]", "", g.group(1))

    elif qid == "sig":
        segs = _segs(t.replace("—", ",").replace(" - ", ", "))
        if segs:
            v["signatory_name"] = segs[0]
        desig = next((s for s in segs[1:] if ROLE.search(s)), "")
        if desig:
            v["signatory_desig"] = desig
        if re.search(r"authorit(?:y|ies)\s+confirm|confirmed\s+authorit|is\s+authoris|is\s+authoriz",
                     low) and not re.search(r"\bnot\b[^.]{0,20}authoris", low):
            v["authority_confirmed"] = True

    elif qid == "prior":
        if re.match(r"\s*(?:no\b|none\b|nil\b)", low):
            v["prior"] = "No"
        elif re.match(r"\s*(?:yes\b|y\b)", low):
            v["prior"] = "Yes"
            ds = find_dates(t)
            if ds:
                v["prior_date"] = ds[0]
            ref = _after(t, r"\b(?:covering|regarding|in respect of|re)\b")
            if ref:
                v["prior_ref"] = ref
            cur = _after(t, r"\bthis (?:one|notice) covers only\b")
            if cur:
                v["current_instrument"] = cur
        elif re.search(r"don'?t know|unsure|not sure|unknown", low):
            v["prior"] = "Don't know"

    elif qid == "inv":
        # Pipe/tab/two-space columns first; prose such as "Tax Invoice No. X
        # dated D for INR A" falls through to the cue-anchored reader, which
        # does not split an Indian-format amount on its own commas.
        rows = _rows_from_lines(t, ["no", "date", "amt"]) or _invoices(t) or _invoices_loose(t)
        if rows:
            v["invoices"] = rows

    elif qid == "soa":
        rows = _rows_from_lines(t, ["ref", "date", "amt"])
        if rows:
            v["soa"] = rows

    elif qid == "who":                                   # consumer: the advocate
        segs = _segs(t)
        if segs:
            v["advocate_name"] = segs[0]
            rest = [s for s in segs[1:] if not re.search(r"notice dated|dated", s, re.I)]
            if rest:
                v["advocate_address"] = ", ".join(rest)
        ds = find_dates(t)
        if ds:
            v["notice_date"] = ds[-1]

    elif qid == "client":
        segs = _segs(t)
        if segs:
            # "Mr Prakash Desai bought CEAT tyres from ..." — the name ends at
            # the verb. Trim the NAME only; the full text still feeds the
            # dealer and product parsers below.
            v["client_name"] = re.sub(
                r"\s+\b(?:bought|purchased|acquired|has|had)\b.*$", "", segs[0], flags=re.I | re.S
            ).strip(" ,;")
        rel = next((s for s in segs[1:] if re.search(r"owner|driver|purchaser|user|consumer", s, re.I)), "")
        if rel:
            v["client_relation"] = rel
        prod = _after(t, r"\b(?:bought|purchased)\b", r"\bfrom\b|[.;\n]")
        if prod:
            v["product"] = prod
        dealer = _after(t, r"\bfrom\b")
        if dealer:
            d = re.sub(r"^(?:m/s\s+)?", "", dealer, flags=re.I)
            # drop the invoice tail: "... , vide Tax Invoice No. STW/2026/1184"
            d = re.split(r"\s*,?\s*\b(?:vide|vide\s+invoice|invoice\s+no)\b", d, flags=re.I)[0]
            v["dealer"] = d.strip(" ,;")
        addr = next((s for s in segs[1:] if ADDR_START.match(s)), "")
        if addr:
            v["client_address"] = addr

    elif qid == "facts":                                 # consumer: CEAT's own facts
        d = _dates_by_cue(t, {"claim_date": r"claim|received|lodg",
                              "rejection": r"communicat|inform|convey|reject"})
        v.update(d)
        ins = _after(t, r"\b(?:on inspection|inspection|found to be|found)\b", r"[.;\n]|, and")
        if ins:
            v["inspection"] = ins

    elif qid == "agr":                                   # breach / termination / renewal / fm / price
        head = re.split(r"\bdated\b", t, 1, flags=re.I)[0]
        head = _segs(head)
        if head:
            v["agreement_name"] = head[0]
        ds = find_dates(t)
        if ds:
            v["agreement_date"] = ds[0]
            if kind == "renewal" and len(ds) > 1:
                v["expiry_date"] = ds[1]
        cl = re.search(r"clause\s*(?:no\.?)?\s*([0-9]+(?:\.[0-9]+)*[A-Za-z]?)", t, re.I)
        if cl:
            v["clause_no"] = cl.group(1)
        if kind == "fm":
            if re.search(r"\bceat\b[^.]{0,40}\binvok", t, re.I):
                v["direction"] = "Invoking"
            elif re.search(r"\brespond", t, re.I):
                v["direction"] = "Responding"

    elif qid == "basis":                                 # price adjustment
        ds = find_dates(t)
        if ds:
            v["agreement_date"] = ds[0]
        head = _segs(re.split(r"\bdated\b", t, 1, flags=re.I)[0])
        if head:
            v["agreement_name"] = head[0]
        cl = re.search(r"clause\s*(?:no\.?)?\s*([0-9]+(?:\.[0-9]+)*[A-Za-z]?)", t, re.I)
        if cl:
            v["clause_no"] = cl.group(1)
        reason = _after(t, r"\b(?:on account of|because of|due to|owing to|reason)\b")
        if reason:
            v["reason"] = reason

    elif qid == "event":                                 # force majeure
        ds = find_dates(t)
        if ds:
            v["fm_date"] = ds[0]
        v["fm_event"] = re.sub(r"\s+", " ", t).strip()

    elif qid == "detail" and kind == "termination":
        v.update(_dates_by_cue(t, {"cure_given_date": r"cure (?:notice|period) (?:given|issued|sent)|cure notice",
                                   "cure_lapsed_date": r"laps|expir|end(?:ed)?"}))

    elif qid == "prices":
        rows = _rows_from_lines(t, ["sku", "old", "nw"])
        if rows:
            v["prices"] = rows

    return {k: x for k, x in v.items() if x not in ("", None, [], {})}


# ------------------------------------------------------- the whole story --
DATE_RX = r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4}"
MONEY_RX = r"[\d][\d,]*(?:\.\d{1,2})?"


def _d(s):
    d = parse_date(s)
    return d.isoformat() if d else ""


def _money(s):
    v = re.sub(r"[^\d.]", "", str(s or ""))
    return v if v not in ("", ".") else ""


def _cheques(t: str) -> list[dict]:
    """Cheque particulars out of a narrative. The phrasing is stereotyped —
    'cheque no. X dated D for INR A drawn on B, dishonoured E for "reason"' —
    so each mention is read as its own block, inheriting 'same bank'."""
    out: list[dict] = []
    parts = re.split(r"(?i)\bcheque\b", t)[1:]
    for raw in parts:
        ch = raw[:420]
        no = re.search(r"(?:no\.?|number|bearing)\s*:?\s*([0-9]{4,12})", ch, re.I) \
            or re.search(r"^[\s:,.#-]*([0-9]{4,12})\b", ch)
        if not no:
            continue
        row = {c: "" for c, _ in (("no", 0), ("date", 0), ("amt", 0), ("bank", 0),
                                  ("dis", 0), ("reason", 0), ("memo", 0))}
        row["no"] = no.group(1)
        m = re.search(r"dated\s+(" + DATE_RX + r")", ch, re.I)
        row["date"] = _d(m.group(1)) if m else ""
        m = (re.search(r"(?:for|of|amounting to|sum of)\s*(?:INR|Rs\.?|₹)\s*(" + MONEY_RX + r")", ch, re.I)
             or re.search(r"(?:INR|Rs\.?|₹)\s*(" + MONEY_RX + r")", ch, re.I)
             or re.search(r",\s*(\d[\d,]{4,})\s*,", ch))
        row["amt"] = _money(m.group(1)) if m else ""
        # The stop-cue list matters: without "issued" the bank field runs on
        # into ", issued by Noticee No" and only stops at the period in "No.".
        m = re.search(r"drawn on\s+(.+?)"
                      r"(?=,?\s*(?:dishonou?r|returned|reason|memo|issued|signed|drawn|"
                      r"bearing|payable|in favour|under the signature)|[.;]|$)", ch, re.I)
        if m:
            row["bank"] = m.group(1).strip(" ,")
        elif re.search(r"same bank", ch, re.I) and out:
            row["bank"] = out[-1]["bank"]
        m = re.search(r"(?:dishonou?red|returned(?:\s+unpaid)?)\s*(?:on\s+)?(" + DATE_RX + r")", ch, re.I)
        row["dis"] = _d(m.group(1)) if m else ""
        r_ = _quoted(ch) or _after(ch, r"\breasons?\b", r"[.;\n]|,\s*cheque")
        row["reason"] = r_.strip(" ,;'\"")
        m = re.search(r"memo\s+(?:dated\s+)?(" + DATE_RX + r")", ch, re.I)
        row["memo"] = _d(m.group(1)) if m else ""
        if row["no"] and (row["amt"] or row["date"]):
            out.append(row)
    return out


# --------------------------------------------------- invoices / directors --
# The number cue below is REQUIRED. Without it the alternation backtracks from
# "invoice" to "inv" on prose such as "Which invoices does the cheque cover?"
# and the capture group swallows the leftover "oices" as an invoice number.
INV_RX = re.compile(r"(?:invoices?|inv|bill)\s*(?:no\.?|number|#)\s*[:\-]?\s*"
                    r"([A-Z0-9][A-Z0-9/\-]{3,24})", re.I)

PERSON_NAME = (r"(?:Mr|Mrs|Ms|Shri|Smt|Sri|Dr|Miss)\.?\s+"
               r"[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,3}")


def _invoices(t: str) -> list[dict]:
    """Invoice rows out of a narrative or a pasted sheet.

    Line-scoped on purpose: the date and the amount are taken from the same
    line that carries the invoice number, never from the first date or the
    first amount found anywhere in the file.
    """
    out, seen = [], set()
    for line in str(t or "").splitlines():
        m = INV_RX.search(line)
        if not m:
            continue
        no = m.group(1).strip(" .,;:")
        if not no or no.lower() in seen:
            continue
        seen.add(no.lower())
        tail = line[m.end():]
        dm = (re.search(r"dated?\s+(" + DATE_RX + r")", tail, re.I)
              or re.search(r"(" + DATE_RX + r")", tail))
        am = (re.search(r"(?:for|of|amounting to|sum of)\s*(?:INR|Rs\.?|\u20b9)\s*("
                        + MONEY_RX + r")", tail, re.I)
              or re.search(r"(?:INR|Rs\.?|\u20b9)\s*(" + MONEY_RX + r")", tail, re.I))
        row = dict(no=no,
                   date=_d(dm.group(1)) if dm else "",
                   amt=_money(am.group(1)) if am else "")
        if row["date"] or row["amt"]:
            out.append(row)
    return out


def _invoices_loose(t: str) -> list[dict]:
    """In the invoice box itself, a line that opens with a reference such as
    'INV/HYD/2026/771 dated … for Rs. …' is an invoice even without the word
    'Invoice'. Same line-scoping as _invoices."""
    out, seen = [], set()
    for line in str(t or "").splitlines():
        m = re.match(r"\s*(?:no\.?\s*)?([A-Za-z0-9][A-Za-z0-9/\-_.]*\d[A-Za-z0-9/\-_]*)", line)
        if not m or parse_date(m.group(1)):
            continue
        no = m.group(1).strip(" .,;:")
        if no.lower() in seen:
            continue
        tail = line[m.end():]
        dm = (re.search(r"dated?\s+(" + DATE_RX + r")", tail, re.I) or re.search(r"(" + DATE_RX + r")", tail))
        am = (re.search(r"(?:for|of|amounting to|sum of)\s*(?:INR|Rs\.?|\u20b9)\s*(" + MONEY_RX + r")", tail, re.I)
              or re.search(r"(?:INR|Rs\.?|\u20b9)\s*(" + MONEY_RX + r")", tail, re.I))
        if not am:
            # "INV-11 02.06.2026 310000": a bare figure after the date
            rest = tail[dm.end():] if dm else tail
            am = re.search(r"(?<![\d.,/])(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d{3,}(?:\.\d{1,2})?)(?![\d.,/])", rest)
        row = dict(no=no, date=_d(dm.group(1)) if dm else "", amt=_money(am.group(1)) if am else "")
        if row["date"] or row["amt"]:
            seen.add(no.lower())
            out.append(row)
    return out


def _directors(t: str, default_addr: str = "") -> list[dict]:
    """Directors named as co-noticees. Only lines that actually say 'director'
    are read, so an authorised signatory mentioned elsewhere is not promoted
    into a noticee. 'same address' inherits the company's address."""
    out, seen = [], set()
    for line in str(t or "").splitlines():
        if not re.search(r"\bdirectors?\b|\bpartners?\b", line, re.I):
            continue
        for m in re.finditer(PERSON_NAME, line):
            name = re.sub(r"\s+", " ", m.group(0)).strip(" ,.")
            if len(name.split()) < 2 or name.lower() in seen:
                continue
            seen.add(name.lower())
            tail = line[m.end():]
            if re.search(r"\bsame address\b", tail, re.I):
                addr = default_addr
            else:
                am = re.search(r"\baddress(?:ed at)?\b\s*[:\-]?\s*(.+?)[.;]*$", tail, re.I)
                addr = am.group(1).strip(" ,.") if am else ""
            out.append(dict(name=name, address=addr))
    return out


def _noticee_type(t: str) -> str:
    """Company or proprietorship. Read wherever the party is described — a
    private limited company must never fall through to the proprietorship
    wording just because the choice widget was left untouched."""
    t = str(t or "")
    if re.search(r"\bpartnership\s+firm\b|\bpartnership\s+act\b|\bpartners?\b", t, re.I):
        return "Partnership + partners"
    if re.search(r"\b(?:sole|individual)\s+propriet|\bproprietorship\b", t, re.I):
        return "Individual / sole proprietor"
    if re.search(r"\bdirectors?\b|\bpvt\.?\s*ltd\b|\bprivate limited\b|"
                 r"\blimited\b|\bllp\b", t, re.I):
        return "Company + directors"
    return ""



def narrative(kind: str, text: str) -> tuple[dict, dict, list]:
    """Read a single free-form account of the matter — the way you would brief
    a colleague — into fields. Cue-anchored only: a value is taken because the
    text names it ("drawn on", "as on", "dishonoured"), never because of where
    it happens to sit. What is not clearly marked stays empty.
    """
    t = str(text or "").strip()
    if not t:
        return {}, {}, []
    v, ev, notes = {}, {}, []
    E = "read from the account you gave"

    def put(k, val, why=E):
        if val not in ("", None, [], {}) and k not in v:
            v[k] = val
            ev[k] = why

    # who
    put("noticee_type", _noticee_type(t))

    # A label with a delimiter, so "…from the same drawer." is not mistaken for
    # "Drawer: Om Enterprises".
    mw = re.search(r"\b(?:drawer|noticee|addressee|addressed to|party|dealer)\b\s*[:\-–—]\s*"
                   r"(.+?)(?=[.;\n]|,\s*address)", t, re.I)
    who = mw.group(1).strip(" ,") if mw else ""
    if who:
        inner = re.search(r"\(([^)]*(?:propriet|director)[^)]*)\)", who, re.I)
        person = ""
        if inner:
            person = re.sub(r"(?i)\b(?:individual|sole)?\s*(?:propriet(?:or|orship)|director)\b[:,\s]*",
                            "", inner.group(1)).strip()
            who = who[:inner.start()].strip(" ,")
        name, firm = _split_party([who, person] if person else [who])
        put("noticee_name", name)
        put("firm_name", firm)
    addr = _after(t, r"\baddress(?:ed at)?\b", r"[.;\n]")
    put("noticee_address", addr)
    if str(v.get("noticee_type", "")).startswith("Company"):
        dirs = _directors(t, v.get("noticee_address", ""))
        if dirs:
            put("directors", dirs, f"{len(dirs)} director(s) named in the account you gave")

    # the instruments
    if kind == "s138":
        inv = _invoices(t)
        if inv:
            put("invoices", inv, f"{len(inv)} invoice(s) described in the account you gave")
        chq = _cheques(t)
        if chq:
            put("cheques", chq, f"{len(chq)} cheque(s) described in the account you gave")
            for col, key in (("dis", "dishonour_date"), ("reason", "dishonour_reason"),
                             ("memo", "memo_date")):
                vals = {c[col] for c in chq if c[col]}
                if len(vals) == 1 and len(chq) == 1:
                    put(key, vals.pop())

    # money
    m = re.search(r"(?:total|aggregat\w+|demanded|outstanding|due|balance|sum of)\D{0,26}"
                  r"(?:INR|Rs\.?|₹)\s*(" + MONEY_RX + r")", t, re.I)
    if m:
        put("amount", _money(m.group(1)))
    elif kind == "s138" and v.get("cheques"):
        tot = sum(float(c["amt"]) for c in v["cheques"] if c["amt"])
        if tot:
            put("amount", str(tot), f"sum of the {len(v['cheques'])} cheques you described")
            notes.append("No separate demand figure was stated, so the amount demanded was taken "
                         "as the total of the cheques described. Confirm it before issue.")

    m = re.search(r"as on\s+(" + DATE_RX + r")", t, re.I)
    if m:
        put("as_on_date", _d(m.group(1)))
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*%", t)
    if m:
        put("interest", m.group(1))
    if re.search(r"\bno\b[^.]{0,30}part[- ]?pay|without any part[- ]?pay", t, re.I):
        pass                                  # explicitly none — leave the field empty
    elif re.search(r"part[- ]?pay", t, re.I):
        put("part_payment", _after(t, r"[^.]*part[- ]?pay", r"[.;\n]") or t)

    # how it goes out, and who signs
    for mode in ("hand delivery", "speed post", "courier", "whatsapp", "email"):
        if re.search(r"\b" + mode.replace(" ", r"\s+") + r"\b", t, re.I):
            put("mode", "BY " + mode.upper())
            break
    # Not _after(): "Mr. A. Verma" is full of full stops, so the line runs to
    # the end of the line and the trailing stop is trimmed afterwards.
    ms = re.search(r"\b(?:signator(?:y|ies)|signed by|to be signed by)\b\s*[:\-–—]?\s*([^\n]+)",
                   t, re.I)
    sig = ms.group(1).strip().rstrip(".").strip() if ms else ""
    if sig:
        segs = _segs(sig.replace("—", ",").replace(" - ", ", "))
        if segs:
            put("signatory_name", segs[0])
        d = next((s for s in segs[1:] if ROLE.search(s)), "")
        put("signatory_desig", d)

    # agreements, for the contract notice types
    m = re.search(r"clause\s*(?:no\.?)?\s*([0-9]+(?:\.[0-9]+)*[A-Za-z]?)", t, re.I)
    if m:
        put("clause_no", m.group(1))
    m = re.search(r"\b(\w[\w\s]{2,40}?agreement)\s+dated\s+(" + DATE_RX + r")", t, re.I)
    if m:
        put("agreement_name", m.group(1).strip().title())
        put("agreement_date", _d(m.group(2)))
    m = re.search(r"jurisdiction\D{0,18}\b(?:at|of|in)\s+([A-Z][A-Za-z]+)", t)
    if m:
        put("jurisdiction", m.group(1))

    return v, ev, notes


def from_text(kind: str, case: dict) -> tuple[dict, dict]:
    """(values, evidence) read out of the free-text answers already in `case`."""
    values, evidence = {}, {}
    for key, raw in list(case.items()):
        if not key.startswith("_raw_") or not str(raw or "").strip():
            continue
        qid = key[len("_raw_"):]
        try:
            got = _parse(kind, qid, raw, case)
        except Exception:                     # a parser must never break the run
            continue
        for k, val in got.items():
            values.setdefault(k, val)
            evidence.setdefault(k, "read from what you typed")
    return values, evidence
