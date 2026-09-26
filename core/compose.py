"""Turning answers into sentences that actually read — and checking the result.

The old drafting step pasted each answer into its template blank verbatim, which
is how notices came out saying "you were obliged to Timely payment…" and "the
Company shall be constrained to If you fail…". This module does three jobs:

1. **Fit** each free-text answer into its sentence. With a model key, the model
   rewrites the answer to fit the gap — and every number and date it returns is
   checked against the answer, so it cannot add a fact. Without a key (or if the
   model's version fails that check) a deterministic fitter works out what shape
   the answer is — a verb phrase, a noun phrase, a clause, or whole sentences —
   and picks the template wording that reads correctly with it.
2. **Lint** the finished notice in code: leftover blanks, doubled full stops,
   capitalised words stranded mid-sentence, repeated sentences, and paragraphs
   that deny and then admit the same point.
3. **Review** the finished notice with the model, which reads the whole thing
   the way a lawyer would and lists problems. It never rewrites anything; what
   it finds goes to the review notes.
"""
from __future__ import annotations
import hashlib
import json
import re

from .words import find_dates, fmt_amount, to_float, to_words

# --------------------------------------------------------------------------
# small text helpers
# --------------------------------------------------------------------------
KEEP_CAPS = {
    "CEAT", "Company", "Noticee", "Noticees", "Agreement", "Clause", "Clauses", "Section",
    "Mr", "Mrs", "Ms", "Shri", "Smt", "Dr", "M", "Goods", "Products", "Said", "I",
    "Indian", "Negotiable", "Bharatiya", "Consumer", "Companies", "GST", "Invoice",
    "Cheque", "Statement", "Dealership", "Supply", "Distributorship", "Technical",
}

BASE_VERBS = {
    "make", "pay", "lift", "settle", "maintain", "purchase", "ensure", "clear", "provide",
    "submit", "achieve", "comply", "keep", "return", "remit", "deposit", "furnish", "not",
    "meet", "honour", "honor", "observe", "perform", "deliver", "supply", "follow", "adhere",
    "abide", "refrain", "procure", "place", "sell", "stock", "display", "renew", "obtain",
    "report", "inform", "notify", "indemnify", "insure", "remain", "use", "cease",
    "discharge", "issue", "take", "give", "carry", "operate", "act", "buy", "order",
    "complete", "raise", "terminate", "initiate", "suspend", "stop", "invoke", "recover",
    "withdraw", "forfeit", "encash", "claim", "seek", "file", "institute", "revoke",
    "appoint", "cancel", "adjust", "debit", "charge", "levy", "block", "hold", "withhold",
    "register", "record", "upload", "lift", "stock", "service", "handle", "process", "verify",
    "inspect", "replace", "refund", "reimburse", "deposit", "top", "extend", "confirm", "treat",
    "grant", "allow", "permit", "restore", "resume", "dispatch", "deliver", "install", "display",
}
PARTICIPLE_PASSIVE = {"appointed", "engaged", "supplied", "introduced", "nominated", "granted",
                      "registered", "onboarded", "authorised", "authorized", "empanelled"}
PARTICIPLE_PROGRESSIVE = {"dealing", "trading", "purchasing", "buying", "operating",
                          "acting", "working", "selling", "distributing"}
PAST_FAILURE = {"failed", "neglected", "defaulted", "refused", "omitted", "breached",
                "stopped", "ceased", "not"}
ROLE_NOUNS = {"dealer", "distributor", "retailer", "sub-dealer", "subdealer", "stockist",
              "wholesaler", "customer", "trader", "franchisee", "agent", "reseller",
              "authorised", "authorized", "channel"}
SENTENCE_STARTERS = {"under", "as", "notwithstanding", "despite", "pursuant", "in", "by", "on",
                     "since", "although", "while", "the", "this", "it", "we", "they", "there",
                     "our", "its", "due", "following", "after", "before", "during", "with",
                     "per", "vide", "further", "moreover", "also", "however"}
CONDITIONAL = re.compile(r"^(?:if|should|in the event|failing|upon failure|on failure|in case)\b",
                         re.I)


def sha(s: str) -> str:
    return hashlib.sha1(str(s or "").encode("utf-8")).hexdigest()[:12]


def money_tidy(t: str) -> str:
    """'INR 284000.00' -> 'INR 2,84,000/-'. Figures already grouped are left alone."""
    def rep(m):
        cur, num = m.group(1), m.group(2)
        v = to_float(num)
        if v is None:
            return m.group(0)
        s = fmt_amount(v)
        tail = "/-" if "." not in s else ""
        return f"{cur} {s}{tail}"
    return re.sub(r"\b(INR|Rs\.?|₹)\s?(\d{4,}(?:\.\d{1,2})?)(?![\d,/])", rep, t)


# A figure right after one of these is money; one right before a unit is not.
_MONEY_LEAD = (r"(?:from|to|of|at|for|towards|upto|up to|deposit|deposits|balance|dues|amount|"
               r"amounts|target|credit|pay|paid|payable|price|sum|value|fee|fees|penalty|charges?|"
               r"worth|exceeding|minimum|maximum|least|refund|reimburse|compensation|security deposit)")
_UNIT_AFTER = (r"(?:units?|days?|kg|kgs|km|kms|tyres?|tubes?|flaps?|metres?|meters?|mm|%|per\s|pcs|"
               r"nos\.?|months?|years?|hours?|weeks?|pieces?|sets?|litres?|liters?)")


def money_full(t: str, words: bool = True) -> str:
    """Figures written as money get Indian grouping, 'INR … /-' and, once, the
    amount in words — the house style the approved notices use. A bare
    '200000' in a revised-terms answer printed as '200000' before this."""
    def rupees(v: float) -> str:
        s_ = f"INR {fmt_amount(v)}" + ("/-" if float(v).is_integer() else "")
        return s_ + (f" ({to_words(v)})" if words else "")

    def bare(m):
        lead, sep, cur, num = m.group(1), m.group(2), m.group(3), m.group(4)
        v = to_float(num)
        if v is None or v < 1000:
            return m.group(0)
        # "for 2026" is a year, not an amount — unless it was written as money
        if not cur and float(v).is_integer() and 1900 <= v <= 2100 and "," not in num:
            return m.group(0)
        return f"{lead}{sep} {rupees(v)}"

    out = re.sub(r"\b(" + _MONEY_LEAD + r")([:\u2014-]?)\s+(INR\s*|Rs\.?\s*|\u20b9\s*)?"
                 r"(\d{4,}(?:\.\d{1,2})?|\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?)(?:/-)?"
                 r"(?!\s*" + _UNIT_AFTER + r")(?!\d)(?![.,/]\d)(?!/)(?!\s*\(Rupees)",
                 bare, t, flags=re.I)
    # already-prefixed amounts: grouping, "/-" and words if not already there
    def prefixed(m):
        v = to_float(m.group(2))
        return m.group(0) if v is None or v < 1000 else rupees(v)
    out = re.sub(r"(?<!\w)(INR|Rs\.?|\u20b9)\s*(\d[\d,]*(?:\.\d{1,2})?)(?:/-)?"
                 r"(?!\s*\(Rupees)(?!\d)(?![.,/]\d)(?!/)", prefixed, out, flags=re.I)
    return out


_ISO_RX = re.compile(r"(?<![\d/])(\d{4})-(\d{2})-(\d{2})(?![\d/])")


def house_dates(t: str) -> str:
    """"to be paid by 2026-12-31" -> "to be paid by 31.12.2026". A stored date
    that reaches free text must still print in the house format."""
    return _ISO_RX.sub(lambda m: f"{m.group(3)}.{m.group(2)}.{m.group(1)}", t)


def contract_text(t: str) -> str:
    """House treatment for the free text in the contract notices."""
    return house_dates(money_full(house_self(house_you(t)[0])))


def clean(raw) -> str:
    t = str(raw or "").replace("\r", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = "\n".join(l.strip() for l in t.split("\n"))
    t = re.sub(r"\n{2,}", "\n", t).strip()
    t = money_tidy(t)
    t = re.sub(r"\.{2,}", ".", t)
    return t


def strip_end(t: str) -> str:
    return t.rstrip(" .;,:")


def lower_first(t: str) -> str:
    m = re.match(r"([A-Za-z][\w'/\-]*)", t)
    if not m:
        return t
    w = m.group(1)
    if (w.isupper() and len(w) > 1) or w in KEEP_CAPS or w.rstrip(".") in KEEP_CAPS:
        return t
    if w[0].isupper() and (len(w) == 1 or not any(c.isupper() for c in w[1:])):
        return t[0].lower() + t[1:]
    return t


def cap_first(t: str) -> str:
    for i, c in enumerate(t):
        if c.isalpha():
            return t[:i] + c.upper() + t[i + 1:]
    return t


def end_stop(t: str) -> str:
    t = t.rstrip()
    return t if t.endswith((".", "!", "?", ":")) else t + "."


def strip_clause_suffix(t: str) -> str:
    """'…per annum, as per Clause 9.1 and Clause 9.2 of the Dealership Agreement'
    — the clause is already cited by the sentence the answer goes into."""
    return re.sub(r",?\s*(?:as per|in terms of|under|pursuant to|as required by)\s+Clauses?\s+"
                  r"[\d.()a-z]+(?:\s*(?:,|and|&)\s*(?:Clause\s+)?[\d.()a-z]+)*"
                  r"(?:\s+of\s+the\s+[A-Z][\w ]*?Agreement)?\s*\.?\s*$", "", t)


def tidy(s: str) -> str:
    """Punctuation left behind by joining approved text to an answer."""
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\.\s*\.(?!\.)", ".", s)
    s = re.sub(r"(?<=[a-z]{3})\.,(?=\s)", ",", s)
    s = re.sub(r",\s*\.", ".", s)
    s = re.sub(r" +([,;:.])(?=\s|$)", r"\1", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+\)", ")", s)
    return s.strip()


def multi_sentence(t: str) -> bool:
    return "\n" in t or bool(re.search(r"[.;!?]\s+[A-Z(•\-]", t))


def first_word(t: str) -> str:
    m = re.match(r"[•\-\s]*([A-Za-z][\w\-]*)", t)
    return m.group(1).lower() if m else ""


def shape(raw: str) -> str:
    """verb | clause | conditional | noun | sentence — what kind of text this is."""
    t = clean(raw)
    fw = first_word(t)
    if CONDITIONAL.match(t):
        return "conditional"
    if multi_sentence(t):
        return "sentence"
    if t.lower().startswith("that you") or fw in ("you", "your"):
        return "clause"
    if fw in BASE_VERBS:
        return "verb"
    if fw in PAST_FAILURE:
        return "failure"
    if fw in SENTENCE_STARTERS:
        return "sentence"
    return "noun"


# --------------------------------------------------------------------------
# model-fitted text stored on the case at analysis time
# --------------------------------------------------------------------------
def fitted(case: dict, slot: str, raw) -> dict | None:
    """The model's fit for this slot — only if it was made from the answer as it
    stands now. An edit to the answer makes the stored fit stale and unused."""
    f = (case.get("_fit") or {}).get(slot)
    if f and f.get("src") == sha(clean(raw)) and f.get("text") is not None:
        return f
    return None


# --------------------------------------------------------------------------
# deterministic fitters — each returns (text, note or "")
# --------------------------------------------------------------------------
def fit_business(raw, case) -> tuple[str, str, str]:
    """(business phrase, a role sentence to move to the background, note)."""
    f = fitted(case, "business", raw)
    if f:
        return f["text"], f.get("extra", ""), ""
    t = strip_end(clean(raw))
    if not t:
        return "", "", ""
    fw = first_word(t)
    low = t.lower()
    if low.startswith(("the business", "business")) or re.match(r"^\w+ing\b", low):
        return lower_first(t), "", ""
    if fw in ROLE_NOUNS or low.startswith(("a dealer", "an authorised", "an authorized",
                                          "a distributor", "an dealer")):
        return ("the business of purchase and sale of the Goods", lower_first(t),
                "The 'nature of business' answer described the relationship (e.g. dealer since…) "
                "rather than a line of business. The standard wording was used for the business and "
                "the relationship was moved into the dealing paragraph — check both.")
    return "the business of " + lower_first(t), "", ""


def _article(t: str) -> str:
    low = t.lower()
    if low.startswith(("a ", "an ", "the ")):
        return t
    return ("an " if low[:1] in "aeiou" else "a ") + t


def fit_dealing(raw, case, subject: str, prefix: str = "That ") -> tuple[str, str]:
    """A 'how the dealing arose' answer as a proper paragraph/sentence.
    `subject` is 'Noticee No. 1' or 'you'."""
    t = strip_end(clean(raw))
    if not t:
        return "", ""
    if t.lower().startswith("that "):
        t = t[5:]
    fw = first_word(t)
    body = t
    verb_be = "were" if subject == "you" else "was"
    have = "have" if subject == "you" else "has"
    if fw in PARTICIPLE_PASSIVE:
        body = f"{subject} {verb_be} {lower_first(t)}"
    elif fw in PARTICIPLE_PROGRESSIVE:
        body = f"{subject} {have} been {lower_first(t)}"
    elif fw in ROLE_NOUNS or t.lower().startswith(("a ", "an ")) and first_word(t[2:]) in ROLE_NOUNS:
        body = f"{subject} {have} been {_article(lower_first(t))}"
    elif fw in ("they", "he", "she"):
        # "they have been a CEAT dealer…" — the notice speaks of the noticee as
        # "you" or "Noticee No. 1", never "they".
        rest = t.split(None, 1)[1] if len(t.split(None, 1)) > 1 else ""
        m = re.match(r"(have|has|are|is|were|was)\b(.*)", rest, re.I | re.S)
        if m:
            one = {"have": "has", "has": "has", "are": "is", "is": "is", "were": "was", "was": "was"}
            many = {"have": "have", "has": "have", "are": "are", "is": "are", "were": "were", "was": "were"}
            v = (many if subject == "you" else one)[m.group(1).lower()]
            body = f"{subject} {v}{m.group(2)}"
        else:
            body = f"{subject} {rest}"
    elif fw in ("you", "your", "we", "our", "noticee", "the", "it"):
        body = lower_first(t) if fw not in ("noticee",) else t
    else:
        body = lower_first(t)
    out = (prefix + body) if prefix else cap_first(body)
    return end_stop(out), ""


def _mentions_only_particulars(raw, case) -> bool:
    """True when the answer just restates invoice/cheque particulars that the
    notice already sets out in its own paragraphs."""
    t = clean(raw)
    if re.search(r"dealer|appoint|agreement|since|distribut|relationship|dealership|"
                 r"purchase order|\bP\.?O\.?\b|franchis|customer", t, re.I):
        return False
    refs = [str(r.get("no", "")).strip() for r in (case.get("invoices") or []) + (case.get("cheques") or [])
            if isinstance(r, dict) and str(r.get("no", "")).strip()]
    return bool(refs) and any(r in t for r in refs)


def fit_background(raw, case, multi: bool) -> tuple[str, str]:
    """The Section 138 'transaction background' paragraph (para 3)."""
    f = fitted(case, "background", raw)
    if f:
        if f.get("mode") == "omit" or not f["text"].strip():
            return "", ("The dealing answer only repeated invoice/cheque particulars already stated "
                        "in the notice, so no separate background paragraph was added.")
        return end_stop(f["text"].strip()), ""
    if not clean(raw):
        return "", ""
    if _mentions_only_particulars(raw, case):
        return "", ("The 'how did the relationship arise' answer only repeated the invoice and cheque "
                    "particulars that paragraphs 5–6 already state, so it was left out rather than "
                    "printed twice. Describe the relationship (e.g. appointed dealer since 2021) to "
                    "include it.")
    return fit_dealing(raw, case, "Noticee No. 1" if multi else "you")


def fit_obligation(raw, case, tpl: str | None) -> tuple[str, str]:
    """Breach para 3. `tpl` is the approved sentence with {{CLAUSE_NO}} already
    filled and {{OBLIGATION}} still open."""
    base = tpl or "In terms of Clause {{CLAUSE}} of the Agreement, you were obliged to {{OBLIGATION}}."
    lead = "you were obliged to {{OBLIGATION}}"
    f = fitted(case, "obligation", raw)
    t = strip_clause_suffix(strip_end(clean(raw))) if not f else strip_end(f["text"])
    if not t:
        return "", ""
    mode = (f or {}).get("mode") or shape(t)
    if mode in ("verb", "inline"):
        return base.replace("{{OBLIGATION}}", lower_first(t)), ""
    if mode == "noun" and lead in base:
        return base.replace(lead, "your obligations included " + lower_first(t)), ""
    # whole sentences, a clause, or anything else: set them out after a colon
    if lead + "." in base:
        return base.replace(lead + ".", "your obligations were as follows: " + end_stop(cap_first(t))), ""
    return base.replace("{{OBLIGATION}}", lower_first(t)), ""


def fit_breach_facts(raw, case, tpl: str | None) -> tuple[str, str]:
    base = tpl or ("You are in breach of the said obligation, in that {{BREACH_FACTS}}. "
                   "Despite the Company's follow-ups, the breach subsists.")
    f = fitted(case, "breach_facts", raw)
    t = strip_end(clean(raw)) if not f else strip_end(f["text"])
    if not t:
        return "", ""
    if t.lower().startswith("that "):
        t = t[5:]
    mode = (f or {}).get("mode") or shape(t)
    if mode in ("clause", "inline"):
        return base.replace("{{BREACH_FACTS}}", lower_first(t)), ""
    if mode == "failure":
        return base.replace("{{BREACH_FACTS}}", "you have " + lower_first(t)), ""
    if mode == "noun":
        return base.replace("{{BREACH_FACTS}}", "there has been " + lower_first(t)), ""
    if ", in that {{BREACH_FACTS}}." in base:
        return base.replace(", in that {{BREACH_FACTS}}.", ". " + end_stop(cap_first(t))), ""
    return base.replace("{{BREACH_FACTS}}", lower_first(t)), ""


def fit_consequences(raw, case, tpl: str | None) -> tuple[str, str]:
    base = tpl or ("Should you fail to cure the breach within the said period, the Company shall be "
                   "constrained to {{CONSEQUENCES}}, at your entire risk as to costs and consequences.")
    f = fitted(case, "consequences", raw)
    t = strip_end(clean(raw)) if not f else strip_end(f["text"])
    if not t:
        return "", ""
    mode = (f or {}).get("mode") or shape(t)
    i = base.find(", at your entire risk")
    risk = base[i:] if i >= 0 else ", at your entire risk as to costs and consequences."
    if mode in ("verb", "inline"):
        return base.replace("{{CONSEQUENCES}}", lower_first(t)), ""
    if mode == "noun":
        return base.replace("{{CONSEQUENCES}}", "proceed with " + lower_first(t)), ""
    if mode == "conditional" and not multi_sentence(t):
        # the answer already states the condition — use it as the sentence
        return cap_first(t) + risk, ""
    lead = base.split("{{CONSEQUENCES}}")[0] if "{{CONSEQUENCES}}" in base else \
        "Should you fail to cure the breach within the said period, the Company shall be constrained to "
    return (lead + "take the following action" + risk.rstrip(".") + ": " + end_stop(cap_first(t))), ""


def fit_inline(raw) -> str:
    """Generic: an answer that goes mid-sentence."""
    return lower_first(strip_end(clean(raw)))


# --------------------------------------------------------------------------
# model fitting (analysis time)
# --------------------------------------------------------------------------
FIT_SLOTS = {
    "s138": {
        "business": dict(
            gap="That you Noticee No. 1, <company>, are a company registered in India engaged in ___; "
                "and Noticee Nos. 2 and 3 … are its directors …",
            guide="Return mode 'inline': a noun phrase naming the line of business, e.g. 'the business "
                  "of purchase and sale of tyres, tubes and flaps'. If the answer also gives history "
                  "(appointed as dealer in a year, credit terms), put that history — as a phrase such "
                  "as 'an authorised dealer of the Company since 2021' — in 'extra', not in 'text'."),
        "background": dict(
            gap="A numbered paragraph that says how the dealing between CEAT and the noticee arose. "
                "Later paragraphs already set out the invoices and the cheque.",
            guide="Return mode 'paragraph': ONE paragraph beginning with 'That', about the relationship "
                  "only. Do not restate invoice numbers, cheque numbers or amounts — those have their "
                  "own paragraphs. If the answer contains nothing except those particulars, return "
                  "mode 'omit' with empty text."),
    },
    "recovery": {
        "relationship": dict(
            gap="Sentence(s) added after: 'That you Noticee No. 1 … are a company … and Noticee Nos. 2 "
                "and 3 … are its directors …' — describing how the dealing arose.",
            guide="Return mode 'sentences': one or two complete sentences, e.g. 'In the year 2021, "
                  "Noticee No. 1 was appointed as an authorised dealer of the Company …'."),
    },
    "breach": {
        "obligation": dict(
            gap="In terms of Clause <n> of the Agreement, you were obliged to ___.",
            guide="Return mode 'inline': a verb phrase beginning with a base-form verb (e.g. 'make "
                  "payment for all Products …'). Do not repeat the clause reference."),
        "breach_facts": dict(
            gap="You are in breach of the said obligation, in that ___. Despite the Company's "
                "follow-ups, the breach subsists.",
            guide="If the facts fit one clause, return mode 'inline' beginning with 'you'. If they need "
                  "several sentences or a list, return mode 'sentences' with complete sentences."),
        "consequences": dict(
            gap="Should you fail to cure the breach within the said period, the Company shall be "
                "constrained to ___, at your entire risk as to costs and consequences.",
            guide="Return mode 'inline': a verb phrase beginning with a base-form verb (e.g. "
                  "'terminate the Agreement for cause under Clause 19.1 and initiate …'). Do not repeat "
                  "the 'if you fail to cure' condition — the sentence already has it."),
    },
}

_FIT_PROMPT = """You are fitting one answer into one gap of a CEAT Limited legal notice.
The notice's surrounding wording is fixed and approved; only the gap changes.

THE GAP:
{gap}

HOW TO FILL IT:
{guide}

THE USER'S ANSWER (the only source of facts):
<<<
{raw}
>>>

ABSOLUTE RULES
- Use only facts in the answer. Keep every name, number, amount, date and clause exactly.
- Add nothing: no new facts, no statutory sections, no Acts, no dates, no amounts.
- Formal Indian legal English. Amounts as 'INR 2,84,000/-'. Dates as DD.MM.YYYY.
- No placeholders, no brackets asking for information.

Return ONLY JSON: {{"mode": "inline" | "sentences" | "paragraph" | "omit", "text": "...", "extra": "..."}}"""


def _nums_dates(t: str) -> tuple[set, set]:
    dates = set(find_dates(t))
    t2 = re.sub(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}\b", " ", t)
    t2 = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}\b", " ", t2)
    nums = set()
    for x in re.findall(r"\d[\d,]*(?:\.\d+)?", t2):
        v = to_float(x)
        if v is not None:
            nums.add(round(v, 2))
    for d in dates:                        # a year or day restated on its own is fine
        y, m, dd = d.split("-")
        nums |= {float(int(y)), float(int(m)), float(int(dd))}
    return nums, dates


def faithful(source: str, out: str) -> tuple[bool, str]:
    """Does `out` contain only numbers/dates that `source` contains, and no
    statutory reference the source did not have?"""
    if "[●" in out or "{{" in out:
        return False, "it left a placeholder"
    sn, sd = _nums_dates(source)
    on, od = _nums_dates(out)
    extra_d = od - sd
    extra_n = {n for n in on - sn if n not in (1.0, 2.0, 3.0)}   # 'Noticee No. 1/2/3'
    if extra_d:
        return False, f"it introduced date(s) not in the answer: {', '.join(sorted(extra_d))}"
    if extra_n:
        return False, f"it introduced figure(s) not in the answer: {', '.join(fmt_amount(n) for n in sorted(extra_n))}"
    for word in ("Section", "Act", "Article", "Rule"):
        if re.search(rf"\b{word}\b", out) and not re.search(rf"\b{word}\b", source):
            return False, f"it cited a '{word}' the answer did not mention"
    if len(out) > 3 * len(source) + 300:
        return False, "it expanded the answer far beyond what was given"
    return True, ""


def llm_fit_case(kind: str, case: dict, chat=None) -> list[str]:
    """Ask the model to fit each free-text answer for this notice type. Results
    are stored on the case under '_fit'; returns notes for the review panel.
    `chat(messages) -> str` is injectable for tests."""
    slots = FIT_SLOTS.get(kind, {})
    if not slots:
        return []
    if chat is None:
        chat = _default_chat
    store = dict(case.get("_fit") or {})
    notes = []
    for slot, spec in slots.items():
        raw = clean(case.get(slot))
        if not raw:
            store.pop(slot, None)
            continue
        key = sha(raw)
        if store.get(slot, {}).get("src") == key:
            continue                                   # already fitted from this exact answer
        try:
            txt = chat([
                {"role": "system", "content": "You fit user answers into approved legal wording. "
                                              "You never add facts. You reply with JSON only."},
                {"role": "user", "content": _FIT_PROMPT.format(gap=spec["gap"], guide=spec["guide"],
                                                               raw=raw)},
            ])
            m = re.search(r"\{.*\}", txt or "", re.S)
            data = json.loads(m.group(0) if m else "{}")
        except Exception as e:                       # the deterministic fitter still runs
            notes.append(f"Wording fit for “{slot}”: model call failed ({type(e).__name__}); "
                         "the built-in fitter was used.")
            continue
        text = str(data.get("text") or "").strip()
        mode = str(data.get("mode") or "inline").strip().lower()
        extra = str(data.get("extra") or "").strip()
        ok, why = faithful(raw, text + " " + extra)
        if not ok:
            notes.append(f"Wording fit for “{slot}” was rejected because {why}; the built-in "
                         "fitter was used instead.")
            store.pop(slot, None)
            continue
        store[slot] = dict(src=key, mode=mode, text=text, extra=extra)
    case["_fit"] = store
    return notes


def _default_chat(messages) -> str:
    from .analyse import _chat, _client
    client, _ = _client()
    rsp = _chat(client, "text", temperature=0, response_format={"type": "json_object"},
                messages=messages)
    return rsp.choices[0].message.content or "{}"


# --------------------------------------------------------------------------
# the read-through
# --------------------------------------------------------------------------
ADMIT_RX = re.compile(r"\b(?:not disputed|not in dispute|matter of record|we admit|is admitted|"
                      r"are admitted|do not dispute|does not dispute|is correct|are correct)\b", re.I)
_CAP_OK = (r"(?:CEAT|Company|Noticee|Noticees|Clause|Clauses|Agreement|Section|INR|Rs|M/s|Mr|Mrs|"
           r"Ms|Shri|Smt|Dr|Goods|Products|Said|Bharatiya|Negotiable|Consumer|Companies|Indian|"
           r"Tax|Invoice|Cheque|Technical|Original|Statement|Dealership|Supply|Cure|Your|You)")
_STRANDED = re.compile(r"\b(obliged to|constrained to|in that|engaged in|called upon to|"
                       r"required to|liable to)\s+(?!" + _CAP_OK + r"\b)([A-Z][a-z]+)")


def blanks(text: str) -> list[str]:
    return [b.strip() for b in re.findall(r"\[●\s*([^\]]*)\]", text or "")]


def lint(text: str) -> list[str]:
    """Drafting errors a reader would see. Warnings only — the lawyer decides."""
    out = []
    for m in _STRANDED.finditer(text):
        a, b = max(0, m.start() - 30), min(len(text), m.end() + 30)
        out.append(f"A sentence breaks mid-way — “…{text[a:b].strip()}…”. An answer seems to have "
                   f"been dropped into the sentence without fitting it.")
    if re.search(r"[a-z)]\.\.(?!\.)", text):
        out.append("A doubled full stop (“..”) appears in the notice.")
    sents = [re.sub(r"\s+", " ", s).strip().lower()
             for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if len(s.strip()) > 60]
    seen, dup = set(), set()
    for s in sents:
        if s in seen:
            dup.add(s)
        seen.add(s)
    for d in list(dup)[:3]:
        out.append(f"The same sentence appears twice: “{d[:90]}…”.")
    for p in text.split("\n"):
        if "deny the contents thereof" in p and ADMIT_RX.search(p):
            out.append("A paragraph says “we deny the contents thereof” and then admits part of the "
                       f"same point — “{p[:110]}…”.")
    return out


_REVIEW_PROMPT = """You are a senior Indian litigation lawyer proof-reading a DRAFT legal notice
issued by CEAT Limited before it is sent. Report problems; do NOT rewrite the notice.

Look only for:
1. contradictions inside the notice (one paragraph says X, another says not-X);
2. statements that conflict with the FACTS below (wrong party in a role, wrong amount, wrong date);
3. broken or ungrammatical sentences, pasted drafting notes, repeated content;
4. amounts or dates that do not agree between paragraphs, or a demand that does not match the facts;
5. anything in square brackets or otherwise left unfinished.

Do NOT comment on CEAT's standard approved wording (the WITHOUT PREJUDICE heading, the BNS
sections, the Companies Act 1956 reference, the standard defence blocks) or on legal strategy.

FACTS HELD FOR THIS NOTICE:
{facts}

THE DRAFT:
<<<
{text}
>>>

Return ONLY JSON: {{"issues": [{{"severity": "high" | "medium" | "low", "where": "...", "problem": "..."}}]}}
Return {{"issues": []}} if you find nothing."""


def ai_review(kind: str, text: str, case: dict, chat=None) -> list[tuple[str, str]]:
    """The model reads the finished notice and lists problems (never rewrites)."""
    if chat is None:
        chat = _default_chat
    facts = {k: v for k, v in case.items()
             if not str(k).startswith("_") and v not in (None, "", [], {}, False)}
    try:
        txt = chat([
            {"role": "system", "content": "You review legal drafts for errors. JSON only."},
            {"role": "user", "content": _REVIEW_PROMPT.format(
                facts=json.dumps(facts, indent=1, default=str, ensure_ascii=False)[:12000],
                text=text[:24000])},
        ])
        m = re.search(r"\{.*\}", txt or "", re.S)
        data = json.loads(m.group(0) if m else "{}")
    except Exception as e:
        return [("warn", f"AI read-through could not run ({type(e).__name__}) — read the draft "
                         "yourself before sending.")]
    out = []
    for it in (data.get("issues") or [])[:10]:
        sev = {"high": "crit", "medium": "warn"}.get(str(it.get("severity", "")).lower(), "info")
        where = str(it.get("where") or "").strip()
        prob = str(it.get("problem") or "").strip()
        if prob:
            out.append((sev, "AI read-through" + (f" ({where})" if where else "") + f": {prob}"))
    return out

# --------------------------------------------------------------------------
# the contract notices (termination, renewal, force majeure, price)
#
# These four types were left on the old "paste the answer into the middle of
# the sentence" path, which produced "you were required to to register…",
# "The expected impact/duration is due to the flooding…" and "and to suspension
# of CEAT's delivery obligations…". Each slot now has a fitter that works out
# the shape of the answer and picks wording that reads correctly with it, and a
# multi-item answer becomes a lettered list instead of a wall of prose.
# --------------------------------------------------------------------------
BULLET = re.compile(r"^\s*(?:[-•*·–]|\(?[a-z]\)|\(?\d{1,2}[.)])\s+", re.I)


SELF_VERB = (r"(?=\s+(?:will|shall|is|was|are|were|has|have|had|proposes|intends|may|can|does|"
             r"did|would|could|remains|continues|expects))")


def house_self(t: str) -> str:
    """The notice calls itself "the Company". An answer that says "CEAT will…"
    or "CEAT's obligation" made the notice speak of itself in the third person
    in the middle of its own sentences."""
    t = re.sub(r"(?<![“\"'])\bCEAT Limited\b(?![”\"'])", "the Company", t)
    t = re.sub(r"(?<![“\"'])\bCEAT['’]s\b", "the Company's", t)
    t = re.sub(r"(?<![“\"'])\bCEAT\b" + SELF_VERB, "the Company", t)
    return t


def as_items(raw) -> list[str]:
    """A multi-item answer -> its items. Lines and bullets first, then
    semicolons, then sentences."""
    t = clean(raw)
    if not t:
        return []
    lines = [l for l in t.split("\n") if l.strip()]
    if len(lines) > 1:
        items = [BULLET.sub("", l) for l in lines]
    elif t.count(";") >= 1:
        items = t.split(";")
    else:
        items = re.split(r"(?<=[.])\s+(?=[A-Z])", t)
    out = [strip_end(i.strip()) for i in items]
    out = [i for i in out if i]
    if len(out) == 1:
        # one long line: "payment of …, removal of …, and return of …"
        commas = comma_items(out[0])
        if commas:
            return [strip_end(c) for c in commas]
    return out


def punctuate(items: list[str], last: str = ".") -> list[str]:
    """Legal list punctuation: semicolons, 'and' before the last, then `last` —
    a full stop when the list ends the sentence, a comma when a closing clause
    follows ("…; and (d) …, are each denied")."""
    if not items:
        return []
    out = []
    for i, it in enumerate(items):
        is_last = i == len(items) - 1
        end = last if is_last else ("; and" if i == len(items) - 2 else ";")
        out.append(strip_end(it) + end)
    return out


def _sub_or_inline(lead: str, items: list[str], joiner: str = " ") -> tuple[str, list[str]]:
    """One item reads inline; several become a lettered list under the lead."""
    if len(items) == 1:
        return strip_end(lead) + joiner + end_stop(items[0]), []
    return strip_end(lead) + ":", punctuate(items)


def fit_required_to(raw, case, clause_txt: str) -> tuple[str, list[str]]:
    """Termination: 'In terms of Clause X, you were required to ___.'"""
    f = fitted(case, "obligation", raw)
    t = strip_end(clean(raw)) if not f else strip_end(f["text"])
    if not t:
        return "", []
    was_to = bool(re.match(r"^to\s+", t, re.I))       # "to register …" is a verb phrase
    items = [re.sub(r"^to\s+", "", i, flags=re.I) for i in as_items(contract_text(t))]
    mode = "verb" if was_to else ((f or {}).get("mode") or shape(items[0] if len(items) == 1 else t))
    lead = f"In terms of Clause {clause_txt}, you were required to"
    if mode in ("verb", "inline") or len(items) > 1:
        return _sub_or_inline(lead, [lower_first(i) for i in items])
    if mode == "noun":
        return _sub_or_inline(f"In terms of Clause {clause_txt}, your obligations included",
                              [lower_first(i) for i in items])
    return (f"In terms of Clause {clause_txt}, your obligations were as follows: "
            + end_stop(cap_first(t))), []


def fit_failed_as(raw, case) -> str:
    """Termination: 'You have failed to do so, as ___.'"""
    f = fitted(case, "facts", raw)
    t = contract_text(strip_end(clean(raw)) if not f else strip_end(f["text"]))
    if not t:
        return ""
    mode = (f or {}).get("mode") or shape(t)
    if mode in ("clause", "inline"):
        return f"You have failed to do so, as {lower_first(t)}."
    if mode == "failure":
        return f"You have failed to do so, in that you have {lower_first(t)}."
    if mode == "noun":
        return f"You have failed to do so, as {lower_first(t)}."
    return "You have failed to do so. " + end_stop(cap_first(t))


def fit_event(raw, case, date_txt: str, clause_txt: str) -> str:
    """Force majeure: 'On/from DATE, ___ has occurred, being an event beyond …'"""
    f = fitted(case, "fm_event", raw)
    t = contract_text(strip_end(clean(raw)) if not f else strip_end(f["text"]))
    if not t:
        return ""
    parts = re.split(r"(?<=[.])\s+(?=[A-Z])", t)
    head, rest = strip_end(parts[0]), " ".join(parts[1:]).strip()
    lead = (f"On {date_txt}, {lower_first(head)} has occurred, being an event beyond the "
            f"Company's reasonable control within the meaning of Clause {clause_txt}.")
    if shape(head) in ("clause", "conditional") or first_word(head) in ("there", "it"):
        lead = (f"On {date_txt}, {lower_first(head)}. That event is beyond the Company's "
                f"reasonable control within the meaning of Clause {clause_txt}.")
    return (lead + (" " + end_stop(cap_first(rest)) if rest else "")).strip()


def fit_affected(raw, case, clause_ref: str = "") -> str:
    """Force majeure: 'the Company is prevented/delayed from performing ___.'"""
    f = fitted(case, "affected", raw)
    t = contract_text(strip_end(clean(raw)) if not f else strip_end(f["text"]))
    if not t:
        return ""
    lead = "As a direct consequence, the Company is prevented or delayed from performing"
    t = re.sub(r"^the Company's\b", "its", t)      # not "performing the Company's obligation"
    if multi_sentence(t):          # only genuinely separate sentences stand alone
        return (f"{lead} its obligations under the Agreement" + (f" at Clause {clause_ref}" if clause_ref else "")
                + ". " + end_stop(cap_first(t)))
    return f"{lead} {lower_first(t)}."


def fit_impact(raw, case) -> str:
    """Force majeure: 'The expected impact/duration is ___.'"""
    f = fitted(case, "impact", raw)
    t = contract_text(strip_end(clean(raw)) if not f else strip_end(f["text"]))
    if not t:
        return ""
    if multi_sentence(t):
        return end_stop(cap_first(t))
    # "production will remain suspended until…" is a clause, not a noun phrase:
    # it needs "is that", or the sentence reads "the duration is production will…"
    if re.search(r"^[\w\s,'’\-()]{0,80}?\b(?:will|shall|is|are|was|were|has|have|remains?|expects?)\b",
                 t, re.I):
        return f"The expected impact and duration is that {lower_first(t)}."
    return f"The expected impact and duration is {lower_first(t)}."


def fit_relief(raw, case, clause_txt: str) -> tuple[str, list[str]]:
    """Force majeure: '… calls upon you to treat the affected obligations as
    suspended …, and to ___.'"""
    f = fitted(case, "relief", raw)
    t = contract_text(strip_end(clean(raw)) if not f else strip_end(f["text"]))
    lead = (f"Accordingly, in terms of Clause {clause_txt}, the Company hereby invokes force majeure "
            "and calls upon you to treat the affected obligations as suspended for the duration of "
            "the event")
    if not t:
        return lead + ".", []
    items = as_items(t)
    if all(shape(i) in ("verb", "inline") for i in items) and len(items) <= 2:
        return strip_end(lead) + ", and to " + ", and to ".join(lower_first(i) for i in items) + ".", []
    return (strip_end(lead) + ", and to confirm the following:",
            punctuate([lower_first(i) for i in items]))


def fit_called_upon(raw, case, slot: str, lead: str, lead_noun: str = "") -> tuple[str, list[str]]:
    """'Upon termination/expiry, you are called upon to ___.' — wind-down items.

    Items written as noun phrases ("removal of all signage") cannot follow
    "called upon to" — that produced "you are called upon to appropriation of
    the security deposit". A noun-phrase list gets a lead that fits it."""
    f = fitted(case, slot, raw)
    t = contract_text(strip_end(clean(raw)) if not f else strip_end(f["text"]))
    if not t:
        return "", []
    items = [lower_first(re.sub(r"^to\s+", "", i, flags=re.I)) for i in as_items(t)]
    nouny = sum(1 for i in items if _LISTY.match(i) and not re.match(
        r"(?:pay|remove|return|cease|refund|deliver|hand|submit|settle|transfer|stop|deposit)\b",
        i, re.I))
    if lead_noun and items and nouny >= max(1, int(0.6 * len(items))):
        return _sub_or_inline(lead_noun, [cap_first(i) for i in items])
    return _sub_or_inline(lead, items)


def fit_terms(raw, case, lead: str) -> tuple[str, list[str]]:
    """Renewal: the revised terms, one per item."""
    f = fitted(case, "revised_terms", raw)
    t = contract_text(strip_end(clean(raw)) if not f else strip_end(f["text"]))
    if not t:
        return strip_end(lead) + ".", []
    items = as_items(t)
    if len(items) == 1:
        return strip_end(lead) + ": " + end_stop(lower_first(items[0])), []
    return strip_end(lead) + ":", punctuate([cap_first(i) for i in items])

# --------------------------------------------------------------------------
# structure: points and tables instead of a wall of prose
#
# An answer that lists things — invoices with amounts, wind-down steps,
# mitigation measures, demands — used to print as one long paragraph with line
# breaks inside it. Every notice type now lays those out as (a), (b), (c)
# points, or as a table with a total when each line carries an amount.
# --------------------------------------------------------------------------
_REF_RX = re.compile(r"(?:invoice|inv|bill|claim|credit note|cn|debit note|dn|order|po|ref|"
                     r"cheque|chq)\.?\s*(?:no\.?\s*)?[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/\-_.]*\d"
                     r"[A-Za-z0-9/\-_.]*)", re.I)
_CODE_RX = re.compile(r"^[•\-*\s]*([A-Za-z0-9][A-Za-z0-9/\-_.]*\d[A-Za-z0-9/\-_.]*)\b")
_AMT_RX = re.compile(r"(?:INR|Rs\.?|\u20b9)\s*([\d,]+(?:\.\d{1,2})?)", re.I)


_SUMMARY_RX = re.compile(r"^\s*(?:the\s+)?(?:total|sub-?total|grand total|aggregate|in all|"
                         r"altogether)\b", re.I)


def _is_item(line: str) -> bool:
    if _SUMMARY_RX.match(line):
        return False                      # a total line closes a list, it is not in it
    if BULLET.match(line):
        return True
    # an unbulleted line counts only if it names something AND carries a figure
    return bool(_AMT_RX.search(line) and (_REF_RX.search(line) or _CODE_RX.match(line)))


def money_sentence_items(text: str) -> list[str]:
    """Three invoices inside one sentence, separated by semicolons or full
    stops, are still a list. "Invoice No. X dated D for INR A…; Invoice No. Y…"
    printed as prose because the splitter only looked at line breaks."""
    t = str(text or "").strip()
    if "\n" in t:
        return []
    chunks = []
    for part in re.split(r";\s*", t):
        # sentences() knows "Invoice No." is not a sentence end
        chunks += [c.strip(" ;") for c in sentences(part) if c.strip(" ;")]
    hits = [c for c in chunks if _AMT_RX.search(c) and _REF_RX.search(c)]
    return hits if len(hits) >= 2 else []


def layout(text: str) -> dict:
    """Split a block of text into a lead sentence, its list items and any
    closing sentence — and, when the items carry amounts, a table."""
    lines = [l.strip() for l in str(text or "").split("\n") if l.strip()]
    flags = [_is_item(l) for l in lines]
    if sum(flags) < 2:
        # the items may be inside one sentence rather than on their own lines
        inline = money_sentence_items(" ".join(lines))
        if inline:
            whole = " ".join(lines)
            first = whole.find(inline[0])
            last = whole.find(inline[-1]) + len(inline[-1])
            return dict(lead=whole[:first].strip(" ;,"), items=inline,
                        tail=whole[last:].strip(" ;,"), table=money_table(inline))
        return dict(lead=" ".join(lines), items=[], tail="", table=None)
    first, last = flags.index(True), len(flags) - 1 - flags[::-1].index(True)
    items = [BULLET.sub("", l).strip() for l in lines[first:last + 1] if l.strip()]
    return dict(lead=" ".join(lines[:first]).strip(), items=items,
                tail=" ".join(lines[last + 1:]).strip(), table=money_table(items))


def money_table(items: list[str]) -> dict | None:
    """Reference / date / amount rows, with a total, when the items are money
    lines. 'Invoice CEAT/PN/2026/0451 dated 18.05.2026, outstanding INR 2,84,000'
    belongs in a table, not in the middle of a sentence."""
    rows, total = [], 0.0
    for it in items:
        am = _AMT_RX.search(it)
        if not am:
            return None
        val = to_float(am.group(1))
        ref_m = _REF_RX.search(it) or _CODE_RX.match(it)
        if not ref_m:
            return None
        ds = find_dates(it)
        due = ""
        dm = re.search(r"(?:due|fell due|payable)\s+(?:on\s+)?([\d./-]{6,12})", it, re.I)
        if dm and find_dates(dm.group(1)):
            due = ".".join(reversed(find_dates(dm.group(1))[0].split("-")))
        rows.append([ref_m.group(1).rstrip(".,;"),
                     ".".join(reversed(ds[0].split("-"))) if ds else "\u2014",
                     due or "\u2014",
                     fmt_amount(val) if val is not None else "\u2014"])
        total += val or 0
    if len(rows) < 2:
        return None
    rows.append(["Total", "", "", fmt_amount(total)])
    return dict(head=["Invoice / reference", "Date", "Due date", "Amount (INR)"], rows=rows)

# --------------------------------------------------------------------------
# long prose -> paragraphs and points
#
# People paste a whole briefing note into one answer box. Before this, that
# printed as a single 430-word paragraph with twelve sentences in it, and a
# comma-separated list of wind-down obligations printed as one 146-word
# sentence. A notice puts one point in one paragraph.
# --------------------------------------------------------------------------
_LISTY = re.compile(r"^(?:payment|removal|return|revocation|cessation|delivery|refund|supply|"
                    r"appropriation|recovery|demand|surrender|handover|hand-over|deposit|"
                    r"submission|settlement|transfer|discontinuance|\w+(?:tion|sion|ment|ance|ence|"
                    r"ure|ing))\b", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\u201c])")
# "Report No. TS/WCA/..." and "Mr. Reddy" are not sentence ends
_ABBREV = re.compile(r"\b(?:No|Nos|Mr|Mrs|Ms|Dr|Shri|Smt|Ltd|Pvt|Co|Corp|Inc|Rs|INR|Sr|Jr|vs|viz|"
                     r"etc|i\.e|e\.g|Cl|Sec|Art|Ref|Dt|Regn|Reg|St|Rd)\.$", re.I)


def sentences(t: str) -> list[str]:
    out = []
    for piece in _SENT_SPLIT.split(str(t or "").strip()):
        piece = piece.strip()
        if not piece:
            continue
        if out and _ABBREV.search(out[-1]):
            out[-1] += " " + piece          # the split was after an abbreviation
        else:
            out.append(piece)
    return out


def comma_items(t: str) -> list[str]:
    """A run of obligations separated by commas — "payment of …, removal of …,
    cessation of …, and return of …" — as separate items. Commas inside
    amounts (2,24,400) never split."""
    raw_parts = [p.strip() for p in re.split(r";\s*|,\s*(?!\d{2,3}\b)", t) if p.strip()]
    raw_parts = [re.sub(r"^and\s+", "", p, flags=re.I) for p in raw_parts]
    if len(raw_parts) < 3:
        return []
    # Only a fragment that starts like a new obligation opens a new item;
    # anything else belongs to the one before it ("removal of all signage,
    # fascia and display material" is one obligation, not two).
    parts = []
    for p in raw_parts:
        if parts and not (_LISTY.match(p) and len(p) > 12):
            parts[-1] += ", " + p
        else:
            parts.append(p)
    if len(parts) < 3:
        return []
    listy = sum(1 for p in parts if _LISTY.match(p) and len(p) > 12)
    if listy < max(3, int(0.6 * len(parts))):
        return []
    return parts


def split_paragraph(text: str, max_words: int = 110) -> list[str]:
    """One long block -> several paragraphs, broken at sentence ends. Anything
    shorter than `max_words` is left exactly as it is."""
    t = str(text or "").strip()
    if len(t.split()) <= max_words:
        return [t]
    out, cur = [], []
    for sent in sentences(t):
        cur.append(sent)
        if len(" ".join(cur).split()) >= max_words * 0.55:
            out.append(" ".join(cur))
            cur = []
    if cur:
        if out and len(" ".join(cur).split()) < 12:      # a stray tail rejoins
            out[-1] += " " + " ".join(cur)
        else:
            out.append(" ".join(cur))
    return out or [t]


_THIRD = re.compile(r"\bthe\s+(Dealer|Distributor|Noticee|Dealership concern)\b(?!\s+Code)", re.I)
_THIRD_POSS = re.compile(r"\bthe\s+(Dealer|Distributor|Noticee)['\u2019]s\b", re.I)


def house_you(t: str) -> tuple[str, bool]:
    """The notice addresses the other side as "you". An answer copied from an
    internal note says "the Dealer was required…", which reads as if the notice
    were about somebody else."""
    out = _THIRD_POSS.sub("your", t)
    out = _THIRD.sub("you", out)
    if out == t:
        return t, False
    # verb agreement after the swap
    for a, b in ((r"\byou was\b", "you were"), (r"\byou has\b", "you have"),
                 (r"\byou is\b", "you are"), (r"\byou does\b", "you do"),
                 (r"\byou wasn't\b", "you weren't"), (r"\bYou was\b", "You were"),
                 (r"\bYou has\b", "You have"), (r"\bYou is\b", "You are")):
        out = re.sub(a, b, out)
    return out, True

