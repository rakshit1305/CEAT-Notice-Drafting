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

from .words import find_dates, fmt_amount, to_float

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
    elif fw in ("you", "your", "we", "our", "noticee", "the", "it", "they"):
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
