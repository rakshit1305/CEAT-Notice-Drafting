"""The checks that run before anything is drafted.

Two layers, deliberately: the model is asked not to invent, and then everything
it returned is re-checked here against arithmetic, dates and the notice type's
own mandatory checklist. A blocker stops the draft; a flag travels with it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta

import re

from . import compose as C
from . import draft as DRAFT
from . import schema as SCHEMA
from . import skill_loader as SK
from .config import MAX_DOC_CHARS, MAX_SHEET_ROWS
from .schema import CRITICAL, TABLE_COLS, effective, is_filled, label, part_paid, rows
from .words import (find_dates as parse_dates_raw, fmt_amount, fmt_date, parse_date, to_float,
                    to_words, words_key)


def parse_dates_in(text: str) -> list:
    """Every date in a piece of free text, as date objects."""
    return [parse_date(d) for d in parse_dates_raw(str(text or ""))]


@dataclass
class Check:
    state: str        # pass | fail | na
    text: str


@dataclass
class Report:
    blockers: list = field(default_factory=list)   # stop the draft
    flags: list = field(default_factory=list)      # (severity, text) — travel with it
    checks: list = field(default_factory=list)
    open_items: list = field(default_factory=list) # render as [● ...]
    annexures: list = field(default_factory=list)
    skill_checklist: list = field(default_factory=list)  # verbatim from SKILL.md/references
    blanks: list = field(default_factory=list)     # [● …] still in the notice — no clean download

    @property
    def ok(self) -> bool:
        return not self.blockers


_UNIT = r"(day|days|week|weeks|month|months)"
# The demand period is the one measured from RECEIPT OF THIS NOTICE. Searching
# the text for the first "within N days" instead found the 30-day credit term in
# the recital, so a discount was measured against the invoice terms.
_DEMAND_RX = re.compile(
    r"within\s+(?:a\s+period\s+of\s+)?(\d{1,3})\s*(?:\(\s*[A-Za-z]+\s*\)\s*)?" + _UNIT +
    r"\b[^.]{0,100}?\breceipt\s+of\s+this\s+notice", re.I)
_DEMAND_WORD_RX = re.compile(
    r"within\s+([A-Za-z]+)\s+" + _UNIT + r"\b[^.]{0,100}?\breceipt\s+of\s+this\s+notice", re.I)
_PERIOD_RX = re.compile(
    r"(?:within\s+)?(?:a\s+period\s+of\s+)?(\d{1,3})\s*(?:\(\s*[A-Za-z]+\s*\)\s*)?" + _UNIT + r"\b",
    re.I)
_WORD_PERIOD = {"seven": 7, "ten": 10, "fourteen": 14, "fifteen": 15, "twenty": 20,
                "thirty": 30, "sixty": 60, "ninety": 90}


def _scale(n: int, unit: str):
    unit = unit.lower()
    if unit.startswith("week"):
        n *= 7
    elif unit.startswith("month"):
        n *= 30
    return n if 0 < n <= 365 else None


def _blank_near(said: str, phrase: str, window: int = 140) -> bool:
    """Is the text right after `phrase` a missing-detail marker?

    A phrase being present is not the same as the paragraph saying anything. "the
    Company shall be constrained to [● the consequences]" contains the phrase and
    states nothing, and a tick against it would be false.
    """
    i = said.find(phrase.lower())
    if i < 0:
        return True
    return "[●" in said[i:i + len(phrase) + window]


def _demand_days(kind: str, case: dict, text: str):
    """How many days the notice itself allows, read out of the drafted text.

    Taken from the notice rather than assumed, so a shortened demand period —
    which the user is free to set — moves the deadline the discount is checked
    against instead of leaving the check measuring a period the notice no
    longer states.
    """
    m = _DEMAND_RX.search(text or "")
    if m:
        return _scale(int(m.group(1)), m.group(2))
    m = _DEMAND_WORD_RX.search(text or "")
    if m and m.group(1).lower() in _WORD_PERIOD:
        return _scale(_WORD_PERIOD[m.group(1).lower()], m.group(2))
    # The cure / notice period fields hold nothing but a period, so a plain
    # search is safe there.
    for src in (str(case.get("cure_period") or ""), str(case.get("notice_period") or "")):
        if not src.strip():
            continue
        m = _PERIOD_RX.search(src)
        if m:
            return _scale(int(m.group(1)), m.group(2))
        m = re.search(r"([A-Za-z]+)\s+" + _UNIT, src, re.I)
        if m and m.group(1).lower() in _WORD_PERIOD:
            return _scale(_WORD_PERIOD[m.group(1).lower()], m.group(2))
    return None


def _sum(rs, key) -> float:
    if not isinstance(rs, list):
        return 0.0
    return sum(to_float(r.get(key)) or 0 for r in rs if isinstance(r, dict))


def missing_critical(kind: str, case: dict) -> list[str]:
    case = effective(kind, case)
    return [label(k) for k in CRITICAL.get(kind, []) if not is_filled(case, k)]


def missing_optional(kind: str, case: dict) -> list[str]:
    """Everything the reference file wants that is still empty and not critical."""
    case = effective(kind, case)
    crit = set(CRITICAL.get(kind, []))
    wanted = {
        "s138": ["background", "invoices", "presented_date", "memo_date", "jurisdiction",
                 "mode", "signatory_name", "notice_date"],
        "recovery": ["relationship", "soa", "interest", "jurisdiction", "mode",
                     "signatory_name", "notice_date"],
        "consumer": ["advocate_address", "client_address", "product", "dealer",
                     "inspection", "paras", "demands", "reply_date", "signatory_name"],
        "breach": ["obligation", "cure_period", "consequences", "agreement_date",
                   "mode", "signatory_name", "notice_date"],
        "termination": ["subject_of", "facts", "wind_down", "agreement_date",
                        "mode", "signatory_name", "notice_date"],
        "renewal": ["clause_no", "renewal_term", "confirm_by", "wind_down",
                    "mode", "signatory_name", "notice_date"],
        "fm": ["affected", "impact", "mitigation", "relief", "agreement_date",
               "mode", "signatory_name", "notice_date"],
        "price": ["reason", "clause_no", "pre_orders", "agreement_date",
                  "mode", "signatory_name", "notice_date"],
    }.get(kind, [])
    return [label(k) for k in wanted if k not in crit and not is_filled(case, k)]


def validate(kind: str, case: dict, docs=None) -> Report:
    r = Report()
    # The notice as it will print, built once. Checklist items are asserted
    # against THIS, not written as literal passes: four of them used to show
    # green whether or not the notice said what they claimed.
    draft_text, draft_blocks, draft_notes = "", [], []
    try:
        _, draft_blocks = DRAFT.build(kind, case, draft_notes)
        draft_text = DRAFT.to_text(kind, case)
    except Exception:
        pass
    said = (draft_text or "").lower()
    case = effective(kind, case)          # a fact on every cheque row counts as known
    ref = SK.notice_ref(kind)
    add_flag = lambda sev, t: r.flags.append((sev, t))
    chk = lambda s, t: r.checks.append(Check(s, t))
    docs = docs or []

    # ---- 1. critical gaps stop the draft ---------------------------------
    for m in missing_critical(kind, case):
        r.blockers.append(f"{m} — the notice cannot state this without it, and it will not be invented.")

    r.open_items = missing_optional(kind, case)

    # ---- 2. tier ---------------------------------------------------------
    if not ref.approved:
        add_flag("warn", SK.nonstandard_warning(kind))

    # ---- 3. standing checks ---------------------------------------------
    if not case.get("authority_confirmed"):
        who = case.get("signatory_name") or "the named signatory"
        add_flag("warn", f"Signing authority not confirmed — check that {who} is currently "
                         f"authorised to sign this notice type.")
    prior = str(case.get("prior", "")).strip().lower()
    if kind in ("s138", "recovery", "breach", "termination") and (not prior or prior.startswith("don")):
        # The skill: if the user doesn't know whether a prior notice exists, say so
        # rather than assuming none. The app used to pre-answer this "No".
        add_flag("warn", "⚠ VERIFY: check for prior notices to this counterparty on this matter — the "
                         "prior-notice question is unanswered, so none has been assumed either way.")
    elif prior.startswith("y"):
        add_flag("warn", "A prior notice exists. The lawyer should review its status — served, period "
                         "expired, complaint filed — alongside this draft; this notice's demand is "
                         "confined to the current instrument.")
    add_flag("info", "Statutory provisions come from CEAT's approved wording. Verify each against "
                     "India Code or India Kanoon before issue; this app does not fetch live statutes.")

    # ---- 3a. verbatim checklist from the skill itself ---------------------
    # The pass/fail checks below are hand-coded per notice type and can drift
    # from SKILL.md over time. This surfaces the skill's own checklist text
    # unchanged, so an edit to the reference file is visible in the app without
    # any code change, and nothing the skill asks for is silently dropped.
    r.skill_checklist = ref.checklist

    # ---- 4. arithmetic ---------------------------------------------------
    amt = to_float(case.get("amount"))

    if kind == "s138":
        chq = rows(case, "cheques")
        chq_total = _sum(chq, "amt")
        # Without this the draft silently falls through to the proprietorship
        # wording, which misdescribes a company and drops the Section 141 case
        # against its directors.
        if not str(case.get("noticee_type", "")).strip():
            r.blockers.append("Noticee type is not set. A company drafted as a proprietorship "
                              "misdescribes the drawer and leaves Section 141 unpleaded. "
                              "Choose company or sole proprietor.")
        elif str(case.get("noticee_type", "")).startswith(("Company","Partnership")) and not rows(case, "directors"):
            r.blockers.append("The drawer is a company but no director is named as a noticee. "
                              "Section 141 liability cannot be pleaded against an unnamed director, "
                              "and the subject line of this notice cites Section 141.")
        chk("pass" if chq else "fail", "Cheque particulars present: number, date, amount, drawn-on bank.")
        chk("pass" if all(case.get(k) for k in ("dishonour_date", "dishonour_reason", "memo_date"))
            else "fail", "Dishonour date, reason and bank memo date present.")
        chk("pass" if amt else "fail", "Amount demanded stated in figures and words.")
        # The demand must be the cheque total less money actually received after
        # dishonour. Previously ANY text in the part-payment box — even "No
        # part-payment has been made…" — counted as an explanation and turned
        # this blocker into a warning, so a ₹4,48,000 invoice total went out as
        # the demand on a ₹2,00,000 cheque.
        paid = part_paid(case)
        if paid is None:
            r.blockers.append("A part-payment is described but its amount is not stated in figures. "
                              "State the amount received (and its date) so the demand can be checked "
                              "against the cheque.")
        elif chq_total and amt is not None:
            expected = round(chq_total - paid, 2)
            if abs(expected - amt) > 0.5:
                why = (f"the cheque total is INR {fmt_amount(chq_total)}" if not paid else
                       f"the cheque total INR {fmt_amount(chq_total)} less the part-payment INR "
                       f"{fmt_amount(paid)} is INR {fmt_amount(expected)}")
                inv_total = _sum(rows(case, "invoices"), "amt")
                hint = (" It equals the invoice total — a Section 138 notice demands the cheque "
                        "amount, not the invoice." if inv_total and abs(inv_total - amt) < 0.5 else "")
                r.blockers.append(f"The demand is INR {fmt_amount(amt)}, but {why}.{hint} A demand "
                                  "that differs from the cheque amount can invalidate the notice.")
                add_flag("crit", f"Demand INR {fmt_amount(amt)} does not match the cheque — {why}.")
            chk("pass" if abs(expected - amt) <= 0.5 else "fail",
                "Amount demanded equals the cheque amount less any part-payment received.")
        if paid and paid >= chq_total > 0:
            r.blockers.append("The part-payment recorded is equal to or more than the cheque total — "
                              "there is nothing left to demand under Section 138. Check the figures.")
        if str(case.get("jurisdiction", "")).strip():
            add_flag("warn", f"Jurisdiction is stated as {case['jurisdiction']}. In a cheque case the court "
                             "is generally where CEAT's bank branch that collected the cheque is located — "
                             "confirm the cheque was presented through a branch there.")
        else:
            add_flag("info", "No jurisdiction paragraph was added (none was given). In a cheque case the "
                             "court is generally where CEAT's collecting bank branch is — add it once that "
                             "is confirmed.")
        # Each cheque carries its own cause of action and its own clock, so the
        # timing is checked cheque by cheque rather than once for the notice.
        memos = []          # (label, date, exact) — exact=False means the return
        for i, c in enumerate(chq, 1):          # date stood in for a missing memo date
            lbl = str(c.get("no") or f"cheque {i}")
            d = parse_date(str(c.get("memo", "")).strip() or case.get("memo_date"))
            if d:
                memos.append((lbl, d, True))
                continue
            d = parse_date(str(c.get("dis", "")).strip() or case.get("dishonour_date"))
            if d:
                memos.append((lbl, d, False))
        if not memos:
            d = parse_date(case.get("memo_date")) or parse_date(case.get("dishonour_date"))
            if d:
                memos.append(("", d, bool(parse_date(case.get("memo_date")))))
        approx = any(not e for _, _, e in memos)

        add_flag("warn", "VERIFY: confirm this notice goes out within the statutory period running from "
                         "receipt of each bank dishonour memo, and that a 15-day demand period is correct "
                         "for this case. The window runs from receipt of the memo, not its date.")
        if approx and memos:
            add_flag("crit", "No bank memo date is recorded. The notice will read “[● bank memo date]”, "
                             "and the statutory window below has been worked out from the return dates "
                             "instead — which is not the same thing. Get the memo dates off the return "
                             "slips before this is issued.")

        nd = parse_date(case.get("notice_date")) or date.today()
        dated = parse_date(case.get("notice_date")) is not None
        if not dated:
            r.blockers.append("No date of notice is set. The 30-day window under proviso (b) to "
                              "Section 138 runs from receipt of the dishonour intimation, so the "
                              "date is operative wording, not a formality — it will not be "
                              "defaulted to today.")
        basis = ("the return dates — no bank memo date is recorded, so the return date has been used"
                 if approx else "the bank memo dates")
        late, window = [], []
        for n, d, _e in memos:
            window.append(f"{n or 'the cheque'}: {fmt_date(d)} → {fmt_date(d + timedelta(days=30))}")
            gap = (nd - d).days
            if gap < 0 and dated:
                r.blockers.append(f"The notice is dated before the dishonour of {n or 'the cheque'} "
                                  f"({fmt_date(d)}). Check the dates.")
            elif gap > 30:
                late.append(f"{n or 'the cheque'} — {fmt_date(d)}, {gap} days")

        if late:
            add_flag("crit",
                     ("On the dates given, the demand would be made well beyond 30 days from "
                      + basis + ", for " + "; ".join(late) + ". "
                      if dated else
                      "No notice date is set, so today's date has been used. On that footing the demand "
                      "would fall well beyond 30 days from " + basis + ", for " + "; ".join(late) + ". ")
                     + "Section 138 proviso (b) requires the demand to be made within 30 days of receipt "
                       "of information of dishonour. Unless the intimations were received materially "
                       "later, the window for these cheques appears to have closed and a notice issued now "
                       "may not support a complaint. This must go to the lawyer before anything is issued.")
            r.blockers.append("On the dates given, the demand falls outside the 30-day window under "
                              "proviso (b) to Section 138 for: " + "; ".join(late)
                              + ". Correct the dates, or take the lawyer's instruction before drafting.")
        elif window:
            add_flag("warn", "The 30-day window on " + basis + " runs — " + "; ".join(window)
                     + ". Verify against the statute and the actual dates of receipt.")

        if len(chq) > 1:
            facts_ok = all(str(c.get("dis", "")).strip() or case.get("dishonour_date") for c in chq) and \
                       all(str(c.get("memo", "")).strip() or case.get("memo_date") for c in chq)
            chk("pass" if facts_ok else "fail",
                "Each cheque has its own return date and bank memo date recorded.")
            add_flag("info", f"This notice covers {len(chq)} cheques. Each is a separate cause of action "
                             "with its own limitation clock; confirm with the lawyer that one composite "
                             "notice is the intended course rather than separate notices.")
        chk("pass" if "section 138" in said and "section 141" in said else "fail",
            "Subject cites Section 138 r/w Section 141, NI Act, 1881.")
        chk("pass" if re.search(r"15 \(fifteen\) days from the date of receipt", said) else "fail",
            "Demand gives 15 (FIFTEEN) days from receipt.")
        chk("pass" if case.get("noticee_type", "").startswith(("Company","Partnership"))
            and rows(case, "directors") else
            ("na" if not case.get("noticee_type", "").startswith(("Company","Partnership")) else "fail"),
            "Company drawer: directors named as noticees; Section 141 applies.")

    if kind == "recovery":
        soa_total = _sum(rows(case, "soa"), "amt")
        if soa_total and amt and abs(soa_total - amt) > 0.5:
            r.blockers.append(f"The statement of account totals INR {fmt_amount(soa_total)} but the demand "
                              f"states INR {fmt_amount(amt)}. Resolve it — neither figure will be adjusted.")
        p, t = to_float(case.get("principal")) or 0, to_float(case.get("tax")) or 0
        if (p or t) and amt and abs(p + t - amt) > 0.5:
            r.blockers.append(f"Principal (INR {fmt_amount(p)}) plus tax (INR {fmt_amount(t)}) does not sum "
                              f"to the demanded total (INR {fmt_amount(amt)}).")
        chk("pass" if amt else "fail", "Recovery amount stated in figures and words with the interest rate.")
        chk("pass" if case.get("as_on_date") else "fail", "Outstanding stated with an as-on date.")
        chk("pass" if abs(soa_total - (amt or 0)) < 0.5 and soa_total else "na",
            "Statement of account total ties to the demanded amount.")
        chk("pass" if case.get("interest") else "fail", "Interest rate stated (CEAT default 8% p.a.).")
        chk("pass" if (re.search(r"10 days from the date of receipt", said)
                       and "civil as well as criminal" in said) else "fail",
            "Demand gives 10 days from receipt; civil and criminal language present.")

        # Invoices not yet due on the notice date. The notice itself says payment
        # was due 30 days from invoice, so demanding a later invoice as unpaid is
        # self-contradicting. (This let ₹3,79,500 go out as "defaulted".)
        nd = parse_date(case.get("notice_date"))
        not_due = []
        for row_ in rows(case, "soa"):
            d0 = parse_date(row_.get("date"))
            if d0 and nd and d0 + timedelta(days=30) > nd:
                not_due.append((row_.get("ref") or "an invoice", d0 + timedelta(days=30),
                                to_float(row_.get("amt")) or 0))
        if not_due:
            tot_nd = sum(x[2] for x in not_due)
            listing = "; ".join(f"{a} (due {fmt_date(b)}, INR {fmt_amount(c)})" for a, b, c in not_due)
            accel = re.search(r"accelerat|entire (?:balance|outstanding)|whole (?:balance|outstanding)",
                              str(case.get("extra_notes") or ""), re.I)
            msg = (f"{len(not_due)} invoice(s) totalling INR {fmt_amount(tot_nd)} were not yet due on the "
                   f"notice date ({fmt_date(nd)}), on the notice's own 30-day terms: {listing}.")
            if accel:
                add_flag("crit", msg + " You noted an acceleration clause — the notice must cite it, or "
                                       "the demand for these invoices contradicts paragraph 6.")
            else:
                r.blockers.append(msg + " Remove them from the demand, date the notice after they fall "
                                        "due, or — if the terms make the whole balance payable on default "
                                        "— say so (with the clause) under ‘Anything else’.")
        ao = parse_date(case.get("as_on_date"))
        if ao and nd and (nd - ao).days > 7:
            add_flag("warn", f"The balance is stated as on {fmt_date(ao)}, {(nd - ao).days} days before the "
                             "notice date. Confirm no payments or credit notes have come in since.")
        pref = str(case.get("prior_ref") or "")
        if str(case.get("prior", "")).lower().startswith("y") and pref:
            overlap = [str(x.get("ref")) for x in rows(case, "soa") if str(x.get("ref") or "").strip()
                       and str(x.get("ref")).strip() in pref]
            if overlap:
                add_flag("crit", f"Invoice(s) {', '.join(overlap)} are in this statement of account AND in the "
                                 "earlier notice. The prior-notice paragraph says this demand excludes that "
                                 "matter, but the full invoice is still claimed here — the lawyer should decide "
                                 "whether to reduce the invoice by the amount covered earlier.")
        if not str(case.get("interest_from") or "").strip():
            add_flag("warn", "Interest is demanded without a start date, so it cannot be computed. Answer "
                             "‘From when does interest run?’.")

    if kind == "consumer":
        paras = rows(case, "paras")
        incoming = str(case.get("incoming") or "")
        import re as _re
        numbered = len(_re.findall(r"(^|\n)\s*\(?\d{1,2}[.)]", incoming))
        if numbered and len(paras) < numbered:
            r.blockers.append(f"The incoming notice has {numbered} numbered paragraphs but only "
                              f"{len(paras)} have responses. Every paragraph must be answered.")
        for p in paras:
            if str(p.get("stance", "")).startswith("Admit"):
                add_flag("warn", f"Para {p.get('n')} is a limited admission — a legal decision with "
                                 "consequences in a later complaint. The lawyer must confirm it.")
        if any(str(p.get("stance", "")).startswith("Admit") for p in paras) and case.get("blk_c") is not False:
            add_flag("crit", "A limited admission is being made while the no-privity block is still "
                             "included. Review — they can contradict each other.")
        if not str(case.get("inspection", "")).strip():
            add_flag("warn", "VERIFY: no inspection finding was supplied, so none is asserted in the reply.")
        # The consumer's slot must hold the consumer. The model once filled it with
        # CEAT's own name and Worli address, and nothing caught it.
        cn = str(case.get("client_name") or "")
        ca = str(case.get("client_address") or "")
        cr = str(case.get("client_relation") or "")
        if re.search(r"\bCEAT\b", cn, re.I) or re.search(r"RPG House|Annie Besant", ca, re.I) \
                or re.match(r"\s*manufactur", cr, re.I):
            r.blockers.append("The consumer's details are CEAT's own (name, address or ‘manufacturer’). "
                              "The client is the consumer the advocate acts for — enter their name and "
                              "address from the incoming notice.")
        nd_, rd_ = parse_date(case.get("notice_date")), parse_date(case.get("reply_date"))
        if nd_ and rd_ and nd_ > rd_:
            r.blockers.append(f"The incoming notice is dated {fmt_date(nd_)}, after the reply date "
                              f"{fmt_date(rd_)}. Check both dates.")
        elif nd_ and rd_ and nd_ == rd_:
            add_flag("crit", f"The incoming notice and the reply carry the same date ({fmt_date(nd_)}). "
                             "Check the date printed on the incoming notice — it is usually earlier.")
        # Block C must not contradict the para-wise answers.
        status = DRAFT.dealer_status(case)
        para_txt = " ".join(str(p.get("text") or "") for p in paras)
        says_auth = re.search(r"(?<!not an )(?<!not our )authori[sz]ed\s+(?:CEAT\s+)?dealer", para_txt, re.I)
        if status == "No" and says_auth and case.get("blk_c") is not False:
            r.blockers.append("Contradiction: block C says the purchase was NOT from an authorised dealer, "
                              "but the para-wise reply calls the dealer ‘authorised’. Correct one of them.")
        if not str(case.get("dealer_authorised") or "").strip():
            add_flag("warn", "Answer ‘Is that dealer an authorised CEAT dealer?’ — block C depends on it.")
        for p in paras:
            if not str(p.get("stance", "")).strip():
                r.blockers.append(f"Para {p.get('n')} has no stance (admit / deny / not aware). Every "
                                  "paragraph needs one.")
        chk("pass" if case.get("notice_date") else "fail",
            "“Re:” line cites the incoming notice's date.")
        chk("pass" if paras and (not numbered or len(paras) >= numbered) else "fail",
            "Every numbered paragraph of the incoming notice is answered.")

    if kind == "termination":
        gap = _days(case.get("cure_lapsed_date"), case.get("notice_date"))
        if gap is not None and gap > 60:
            add_flag("crit", f"The cure period lapsed {gap} days ago. A gap this long invites an argument "
                             "that CEAT affirmed the contract — consider a fresh cure notice first.")
        if str(case.get("dues", "")).strip():
            add_flag("warn", "This termination also asserts dues. Confirm whether a separate recovery or "
                             "cure notice should go first — bundling can undercut both.")
        chk("pass" if case.get("clause_no") else "fail", "Termination clause cited.")
        chk("pass" if case.get("effective_date") else "fail", "Effective date given.")

    if kind == "renewal":
        lead = _days(case.get("notice_date"), case.get("expiry_date"))
        if lead is not None and lead < 30 and case.get("intent") == "Do not renew":
            add_flag("crit", f"Only {lead} days remain before expiry. Check the contractual notice period "
                             "— a late non-renewal notice may be ineffective.")
        chk("pass" if case.get("intent") else "fail", "Renew / do-not-renew chosen and reflected throughout.")

    if kind in ("breach", "termination", "renewal", "fm", "price"):
        add_flag("warn", "VERIFY the clause number and any notice period against the actual signed "
                         "agreement — this app does not read clause numbering as authoritative.")

    # A proprietorship is not a separate legal person: the notice must name the
    # proprietor. The breach notice went out to "M/s Deccan Auto Tyres,
    # Proprietor, M/s Deccan Auto Tyres" with no person named at all.
    if kind != "consumer" and str(case.get("noticee_type", "")).startswith("Individual"):
        nm, fm = str(case.get("noticee_name") or "").strip(), str(case.get("firm_name") or "").strip()
        firmish = re.search(r"^\s*m/?s\b|\b(?:tyres?|traders?|enterprises?|agenc(?:y|ies)|motors|"
                            r"automobiles?|& co|company|stores?|sales)\b", nm, re.I)
        if nm and (firmish or (fm and nm.lower() == fm.lower())):
            r.blockers.append(f"“{nm}” is a firm name, but the noticee is marked as a sole proprietor. Name "
                              "the proprietor (the individual) — a proprietorship is not a separate legal "
                              "person, and a notice to the firm alone can be challenged.")

    # ---- the mandatory checklists of the four non-standard types ----------
    nd0 = parse_date(case.get("notice_date"))
    if kind == "termination":
        ocl = str(case.get("obligation_clause") or "").strip()
        tcl = str(case.get("clause_no") or "").strip()
        if str(case.get("ground", "")).startswith("Breach"):
            chk("pass" if ocl else "fail", "The clause imposing the obligation is identified.")
            if ocl and tcl and ocl == tcl:
                add_flag("warn", f"The obligation and the right to terminate are both cited to Clause "
                                 f"{tcl}. In most agreements these are different clauses — check.")
            lapsed = parse_date(case.get("cure_lapsed_date"))
            if lapsed and nd0 and (nd0 - lapsed).days > 45:
                add_flag("crit", f"The cure period lapsed on {fmt_date(lapsed)}, {(nd0 - lapsed).days} "
                                 "days before this notice. A long gap lets the other party argue CEAT "
                                 "carried on dealing with them and waived the breach — consider a fresh "
                                 "cure notice first.")
        eff = parse_date(case.get("effective_date"))
        if eff and nd0 and eff < nd0:
            r.blockers.append(f"Termination is stated to take effect on {fmt_date(eff)}, before the "
                              f"notice date {fmt_date(nd0)}. An agreement cannot be terminated "
                              "retrospectively by notice.")
        elif eff and nd0 and eff == nd0:
            add_flag("warn", "Termination takes effect on the date of the notice itself. Most agreements "
                             "run the effect from receipt — confirm the clause allows same-day effect.")
        add_flag("warn", "⚠ VERIFY the termination clause, the required notice period and any cure "
                         "requirement against the signed agreement.")
        # "governing termination of the Agreement for fraudulent claims" describes
        # this notice, not what the agreement covers.
        sub_ = str(case.get("subject_of") or "").strip()
        if sub_ and re.search(r"^\s*(?:termination|notice|breach|cancellation|recovery)\b|"
                              r"\bfor (?:submission of|submitting|false|fraudulent)\b", sub_, re.I):
            add_flag("crit", "“What the agreement governs” reads like the purpose of this notice "
                             f"(“{sub_[:60]}…”). It should describe the arrangement itself — the "
                             "appointment, the territory, the dealer code, what the dealer did.")

        # A fraud/audit-based termination that counts items should annex them.
        fct = str(case.get("facts") or "")
        m_ = re.search(r"\b(\d{2,})\s+(claims?|invoices?|items?|instances?|transactions?|entries)\b",
                       fct, re.I)
        if m_ and not re.search(r"schedule|annexure|enclosed|annexed", fct + str(case.get("extra_notes") or ""),
                                re.I):
            add_flag("warn", f"The facts rely on {m_.group(1)} {m_.group(2).lower()} but no schedule of "
                             "particulars is mentioned. For a termination of this kind the particulars "
                             "(reference, date, amount, finding) are the evidence — annex them as a "
                             "Schedule and refer to it here.")

        # the same content in two paragraphs
        facts_t = re.sub(r"\W+", " ", str(case.get("facts") or "")).lower()
        wind_t = re.sub(r"\W+", " ", str(case.get("wind_down") or "")).lower()
        shared = [w for w in set(facts_t.split()) & set(wind_t.split()) if len(w) > 6]
        if len(shared) >= 8:
            add_flag("warn", "The breach facts and the wind-down answer overlap heavily, so the notice "
                             "may say the same thing twice. Keep what happened in the facts and what "
                             "they must now do in the wind-down.")

    # Internal approvals belong in the file, not in a notice to the other side.
    told = " ".join(str(case.get(k) or "") for k in
                    ("facts", "breach_facts", "detail", "extra_notes", "wind_down"))
    if re.search(r"internal approval|approval (?:was )?(?:obtained|granted|received)|zonal head|"
                 r"management approval|legal has cleared|approved by the (?:zonal|regional|national)",
                 told, re.I):
        add_flag("crit", "The facts mention an internal approval (who inside CEAT cleared this). "
                         "That is not the other side's business and should not appear in the notice "
                         "— take the sentence out of the answer.")

    if kind == "fm":
        fmd = parse_date(case.get("fm_date"))
        if fmd and nd0:
            gap = (nd0 - fmd).days
            if gap < 0:
                r.blockers.append("The force majeure event is dated after this notice. Check the dates.")
            else:
                add_flag("warn" if gap > 7 else "info",
                         f"The event began {fmt_date(fmd)} and this notice is dated {fmt_date(nd0)} — "
                         f"{gap} day(s) later. ⚠ VERIFY the notice deadline in Clause "
                         f"{case.get('clause_no') or '—'}: force majeure claims are frequently lost for "
                         "late or non-conforming notice.")
        qty = rows(case, "quantities")
        if qty:
            nums = {re.sub(r"[^\d]", "", str(r.get(k) or "")) for r in qty for k in ("sched", "done", "pend")}
            aff_nums = set(re.findall(r"\d{2,}", str(case.get("affected") or "")))
            if len(nums & aff_nums) >= 2:
                add_flag("info", "The affected-obligations answer repeats figures that now appear in the "
                                 "quantities table. Trimming the sentence keeps the notice tighter; the "
                                 "table is the harder record.")
        else:
            add_flag("info", "No quantities table was given. If the affected deliveries can be listed "
                             "(period, scheduled, delivered, pending, due date), a table is much harder "
                             "to dispute later than the same figures in a sentence.")
        for f_, what in (("fm_event", "the event"), ("affected", "the affected obligations"),
                         ("impact", "the expected impact or duration"),
                         ("mitigation", "the mitigation steps"), ("relief", "the relief sought")):
            chk("pass" if str(case.get(f_) or "").strip() else "fail", f"Notice states {what}.")

    if kind == "renewal":
        exp = parse_date(case.get("expiry_date"))
        if case.get("intent") == "Do not renew":
            per = str(case.get("notice_period") or "").strip()
            m = re.search(r"(\d{1,3})\s*(day|month)", per, re.I)
            if m and exp and nd0:
                days = int(m.group(1)) * (30 if m.group(2).lower().startswith("month") else 1)
                if (exp - nd0).days < days:
                    r.blockers.append(
                        f"The agreement needs {per} notice of non-renewal, but only "
                        f"{(exp - nd0).days} day(s) remain to expiry on {fmt_date(exp)}. A late "
                        "non-renewal notice is usually ineffective — check the clause before sending.")
            elif not per:
                add_flag("warn", "No notice period was given for the non-renewal. ⚠ VERIFY the period "
                                 "the clause requires — a late non-renewal notice is often time-barred.")
        else:
            by = parse_date(case.get("confirm_by"))
            if by and exp and by > exp:
                r.blockers.append(f"Acceptance is asked for by {fmt_date(by)}, after the Agreement "
                                  f"expires on {fmt_date(exp)}. Bring the confirm-by date forward.")
            if by and nd0 and by < nd0:
                r.blockers.append("The confirm-by date is before the notice date.")
            chk("pass" if by else "fail", "A date to confirm acceptance is given.")

    if kind == "price":
        eff = parse_date(case.get("effective_date"))
        if eff and nd0 and eff <= nd0:
            r.blockers.append(
                f"The revised prices are stated to take effect on {fmt_date(eff)}, on or before the "
                f"date of this notice ({fmt_date(nd0)}). A price revision applies only after notice "
                "— set the effective date, or change the notice date.")
        # The cut-off named in the pre-orders answer IS the effective date. A
        # notice that says "effective 25.09.2026" and then "orders accepted
        # before 01.11.2026 keep the old price" contradicts itself.
        cut = re.search(r"(?:before|prior to|until|up ?to|on or before)\s+([\d./-]{6,12})",
                        str(case.get("pre_orders") or ""), re.I)
        cut_d = parse_date(cut.group(1)) if cut else None
        if eff and cut_d and cut_d != eff:
            add_flag("crit", f"The notice takes effect on {fmt_date(eff)}, but the answer about "
                             f"orders already placed uses {fmt_date(cut_d)} as the cut-off. One of "
                             "the two is wrong.")
        elif eff and nd0 and (eff - nd0).days < 30:
            add_flag("warn", f"Only {(eff - nd0).days} day(s) between this notice and the effective "
                             "date. ⚠ VERIFY the notice period the price-variation clause requires.")
        if not rows(case, "prices") and not str(case.get("price_change_pct") or "").strip():
            r.blockers.append("Revised prices — give the product-wise table (SKU | existing | revised | "
                              "% change), or at least the overall percentage. The notice cannot state a "
                              "price revision without one of them.")
        chk("pass" if (rows(case, "prices") or case.get("price_change_pct")) else "fail",
            "Revised prices stated, with old versus new or the percentage.")
        chk("pass" if str(case.get("pre_orders") or "").strip() else "fail",
            "Treatment of orders already placed is addressed.")

    if kind == "cnd":
        right = str(case.get("cnd_right") or "").strip()
        acts = str(case.get("cnd_acts") or "").strip()
        stop = str(case.get("cnd_stop") or "").strip()
        # Asserted against the drafted notice, not against the answer boxes. A
        # tick that only means "the field is not empty" passes on a notice whose
        # template dropped the paragraph — which is how a checklist of green
        # ticks once sat above a notice missing its demand.
        chk("pass" if (right and "exclusively entitled to" in said
                       and not _blank_near(said, "exclusively entitled to")) else "fail",
            "The right asserted is identified, and the basis on which CEAT holds it.")
        # "You are infringing our trademarks" asserts nothing a court can act on.
        # Particulars are what, where and since when.
        has_where = bool(re.search(r"\b(?:at|in|on|from|near)\b.{3,}", acts)) or bool(
            re.search(r"https?://|\bwww\.|\bshop\b|\bstore\b|\baddress\b|\bpremises\b", acts, re.I))
        has_when = bool(parse_dates_in(acts)) or bool(
            re.search(r"\bsince\b|\bfrom\b|\bafter\b|\b20\d\d\b", acts, re.I))
        chk("pass" if (len(acts) >= 40 and (has_where or has_when)) else "fail",
            "The offending acts are particularised — what, where and since when.")
        if acts and len(acts) < 40:
            add_flag("crit", "The offending acts are described in one short phrase. A cease and "
                             "desist stands or falls on particulars: what is being done, where, "
                             "since when, and how it came to CEAT's notice. As drafted this is an "
                             "assertion, not evidence of one.")
        elif acts and not (has_where or has_when):
            add_flag("warn", "The offending acts name neither a place nor a date. Add where it is "
                             "happening and since when — the other side's first answer will be to "
                             "deny it, and the notice should already answer that.")
        chk("pass" if (stop and "cease and desist from" in said
                       and not _blank_near(said, "cease and desist from")) else "fail",
            "Each act that must stop is spelt out, so compliance can be measured.")
        chk("pass" if ("confirm in writing" in said and "receipt of this notice" in said
                       and not _blank_near(said, "confirm in writing")) else "fail",
            "A written undertaking is demanded, within a period running from receipt.")
        chk("pass" if ("shall be constrained to" in said
                       and not _blank_near(said, "shall be constrained to")) else "fail",
            "Consequences of non-compliance are stated.")
        chk("pass" if "expressly reserved" in said else "fail",
            "Rights-reserved / without-prejudice line is present.")
        # A registration asserted with no number is the commonest way one of
        # these notices gets answered with "prove it".
        if re.search(r"\bregistered\b|\bregistration\b", right, re.I) and not re.search(
                r"\b(?:no\.?|number|#)\s*[:\-]?\s*\d{4,}|\b\d{5,}\b", right, re.I):
            add_flag("warn", "A registered right is asserted but no registration number is given. "
                             "⚠ VERIFY the number, class and current status against CEAT's records "
                             "and state them — an unparticularised registration invites a denial.")
        seen = parse_date(case.get("cnd_first_noticed"))
        if seen and nd0 and seen > nd0:
            r.blockers.append(
                f"The infringement is said to have been noticed on {fmt_date(seen)}, after the date "
                f"of this notice ({fmt_date(nd0)}). Check the dates.")
        if seen and nd0 and (nd0 - seen).days > 365:
            add_flag("warn", f"{(nd0 - seen).days} days have passed since CEAT noticed the "
                             "infringement. Delay is the standard defence to an injunction — "
                             "⚠ VERIFY with counsel whether the notice should explain it.")
        add_flag("info", "Cease and desist: the right asserted, the statute relied on and the "
                         "relief threatened are matters for counsel. ⚠ VERIFY whether this notice "
                         "should issue from CEAT or through its advocates — that changes the "
                         "closing and the signature block.")

    if kind == "generic":
        # No type-specific wording exists, so the checks are the structural ones
        # any notice needs. This is a drafting aid for a lawyer and the banner
        # on the draft says so.
        subj_ok = bool(re.search(r"(?m)^sub:\s*\S", draft_text or "", re.I)) and \
            not re.search(r"(?mi)^sub:.*\[●", draft_text or "")
        chk("pass" if subj_ok else "fail", "A subject line that says what the notice is.")
        chk("pass" if (str(case.get("gen_facts") or "").strip()
                       and "[● the facts]" not in said) else "fail",
            "The facts are stated.")
        # The deadline sits between "calls upon you" and the "to", so the phrase
        # to anchor on is the shorter one and the window has to reach past it.
        chk("pass" if ("calls upon you" in said
                       and not _blank_near(said, "calls upon you", 200)) else "fail",
            "What is required of the other side is stated, in terms that can be complied with.")
        chk("pass" if (("receipt of this notice" in said or "on or before" in said)
                       and not re.search(r"within \[●", said)) else "fail",
            "A period or date is given, running from receipt.")
        chk("pass" if ("shall be constrained to" in said
                       and not _blank_near(said, "shall be constrained to")) else "fail",
            "Consequences of non-compliance are stated.")
        chk("pass" if "expressly reserved" in said else "fail",
            "Rights-reserved / without-prejudice line is present.")
        add_flag("crit", "This is a generic draft. It has no approved wording and no checks of its "
                         "own beyond the structural ones above — no statutory period is computed, "
                         "no arithmetic is verified against a template. A lawyer must read the "
                         "whole notice before it is issued.")
        # The one way to misuse this tab is to pick it to avoid the questions a
        # real type would ask.
        said_all = " ".join(str(case.get(k) or "") for k in
                            ("gen_title", "gen_subject", "gen_facts", "gen_demand")).lower()
        for rx, better in ((r"\b(?:cheque|chq)\b.{0,40}\b(?:dishonou?r|bounce|returned unpaid)|"
                            r"\bsection\s*138\b|\bnegotiable instruments\b", "Section 138 notice"),
                           (r"\bcease\s+and\s+desist\b|\binfring", "Cease and desist notice"),
                           (r"\bterminat", "Termination notice"),
                           (r"\bforce\s+majeure\b", "Force majeure notice"),
                           (r"\bconsumer\s+(?:forum|commission|notice)\b", "Reply to a consumer notice")):
            if re.search(rx, said_all):
                add_flag("crit", f"This reads like a matter the {better} tab is built for. That tab "
                                 "carries the approved or structured wording and its own checklist; "
                                 "this one carries neither. Use it unless there is a reason not to.")
                break

    if kind in ("breach", "termination"):
        # clauses named in the facts but not in the citation, and the reverse
        said_cl = set(re.findall(r"clauses?\s+(\d+(?:\.\d+)*(?:\([a-z0-9]+\))?)",
                                 " ".join(str(case.get(k) or "") for k in
                                          ("obligation", "facts", "breach_facts", "consequences")),
                                 re.I))
        given = set(re.findall(r"\d+(?:\.\d+)*(?:\([a-z0-9]+\))?",
                               str(case.get("obligation_clause") or case.get("clause_no") or "")))
        extra = sorted(said_cl - given)
        if extra and given:
            add_flag("crit", f"The facts rely on Clause(s) {', '.join(extra)}, but the notice cites "
                             f"Clause(s) {', '.join(sorted(given))} as the obligation. A notice that "
                             "cites one clause and proves another is easy to answer — make them agree.")

    if kind == "breach":
        cited = re.findall(r"\d+(?:\.\d+)*[a-z]?", str(case.get("clause_no") or ""))
        said = " ".join(str(case.get(k) or "") for k in ("obligation", "breach_facts", "consequences"))
        unexplained = [c for c in cited if c not in said and len(cited) > 1]
        if unexplained:
            add_flag("warn", f"Clause(s) {', '.join(unexplained)} are cited as breached but not explained "
                             "anywhere in the notice. Say what each requires, or drop it from the citation.")

    # ---- 4b. early payment discount --------------------------------------
    # The discount is a without-prejudice settlement offer sitting next to a
    # demand. Everything that could make the two contradict each other is a
    # blocker, because a notice that demands one figure and offers a lower one
    # on terms that have already lapsed is worse than no offer at all.
    disc_asked = any(str(case.get(k) or "").strip() for k in
                     ("discount_pct", "discount_amt", "discount_by"))
    if disc_asked:
        base = amt
        if kind == "termination":
            base = to_float(case.get("dues"))
            if base:
                base -= to_float(case.get("deposit_held")) or 0
        elif kind == "breach":
            base = to_float(case.get("dues")) or amt
        if kind == "s138":
            r.blockers.append(
                "An early payment discount has been entered on a Section 138 notice. The statutory "
                "demand must be for the amount of the dishonoured cheque; demanding or accepting "
                "less in the notice itself puts the notice at risk. Remove the discount, or make "
                "the offer in a separate without-prejudice letter.")
        elif not base:
            r.blockers.append(
                "A discount is offered but there is no sum demanded to apply it to. Enter the "
                "amount first — the discounted figure is calculated from it, never typed.")
        else:
            d = SCHEMA.discount(case, base)
            pct_in = to_float(case.get("discount_pct"))
            amt_in = to_float(case.get("discount_amt"))
            if pct_in is not None and amt_in is not None:
                r.blockers.append(
                    "Both a percentage and a flat discount are entered. Give one or the other — "
                    "two discounts on the same sum cannot both be the offer.")
            elif d is None:
                r.blockers.append(
                    "A discount date is given but no discount. Enter the percentage or the flat "
                    "sum, or clear the date.")
            elif d.get("bad"):
                r.blockers.append(
                    f"The discount of INR {fmt_amount(d['off'])} is not less than the sum demanded "
                    f"(INR {fmt_amount(base)}). That is a waiver, not a discount.")
            else:
                if pct_in is not None and not (0 < pct_in < 100):
                    r.blockers.append(f"A discount of {pct_in:g}% is not a discount. "
                                      "Enter a percentage between 0 and 100.")
                by = parse_date(case.get("discount_by"))
                if not by:
                    r.blockers.append(
                        "The discount has no date by which payment must be received. An open-ended "
                        "offer never lapses and cannot be withdrawn cleanly.")
                else:
                    nd = parse_date(case.get("notice_date"))
                    if nd and by <= nd:
                        r.blockers.append(
                            f"The discount lapses on {fmt_date(by)}, on or before the date of the "
                            "notice itself. It would be expired when the notice is served.")
                    # The offer must not outlive the demand period it sits beside.
                    days = _demand_days(kind, case, draft_text)
                    if nd and days:
                        last = nd + timedelta(days=days)
                        if by > last:
                            r.blockers.append(
                                f"The discount runs to {fmt_date(by)}, past the {days}-day period "
                                f"the notice allows (which ends {fmt_date(last)}). The offer would "
                                "outlive the demand it is attached to. Bring it forward.")
                add_flag("info",
                         f"An early payment discount is offered: INR {fmt_amount(d['net'])} if "
                         f"received by {fmt_date(d['by']) or '[no date]'}, against the demand of "
                         f"INR {fmt_amount(base)}. It is worded as a without-prejudice settlement "
                         "offer and does not reduce the sum demanded. Confirm the offer and the "
                         "figure are approved before the notice goes out.")

    # ---- 5. figures and words must agree ---------------------------------
    # Compared on the number words alone: a missing "Rupees" prefix or "Only"
    # is a formatting difference that house_words() fixes at draft time, not a
    # mismatch between the figure and the words.
    if amt and str(case.get("amount_words", "")).strip():
        if words_key(case["amount_words"]) != words_key(to_words(amt)):
            r.blockers.append(f"The amount in words does not match the figure. INR {fmt_amount(amt)} reads "
                              f"as “{to_words(amt)}”, but the notice would say “{case['amount_words']}”.")

    chk("pass" if str(SK.review_banner() or "").strip() else "fail",
        "Every output carries the review banner and is a draft for legal review.")

    # ---- 6. annexures -----------------------------------------------------
    r.annexures = {
        "s138": ["copy of the dishonoured cheque(s)", "copy of the bank return memo",
                 "copies of the invoices referred to"],
        "recovery": ["copies of the invoices in the statement of account",
                     "ledger extract as on the stated date"],
        "consumer": ["copy of the incoming consumer notice", "inspection report, if relied upon"],
    }.get(kind, ["copy of the executed agreement", "copies of the correspondence relied upon"])
    for d in docs:
        r.annexures.append(f"{d.name}" + ("" if d.kind in ("tables", "text") else " (attached, not read)"))

    # ---- 7. truncated sources -------------------------------------------
    # A sheet longer than MAX_SHEET_ROWS is cut before the model ever sees it.
    # Any amount derived from it is then derived from part of the file, and no
    # arithmetic check above can catch that — the sums tie to each other while
    # all of them omit the same rows. So it stops the draft rather than warns.
    for d in docs:
        dropped = getattr(d, "dropped_rows", 0)
        if dropped:
            r.blockers.append(
                f"{d.name}: {dropped} row(s) were not read — the file is longer than the "
                f"{MAX_SHEET_ROWS}-row limit. Any amount taken from it would be computed from "
                f"part of the file. Raise MAX_SHEET_ROWS, or attach a filtered extract "
                f"containing only this counterparty's rows."
            )
        elif getattr(d, "dropped_chars", 0):
            add_flag("warn", f"{d.name}: the end of this document was not read (over the "
                             f"{MAX_DOC_CHARS}-character limit). Check nothing relied on sits past the cut.")
    # ---- 7. statement of account must belong to this counterparty ---------
    # The ledger the app reads usually covers every dealer. If rows from other
    # customers survive into this notice they disclose a third party's data and
    # inflate the demand, so both are stopped here rather than flagged.
    soa = rows(case, "soa")
    if soa:
        # The rows carry "amt" (see TABLE_COLS), not "amount" — summing the
        # wrong key returned 0 and this check silently never fired.
        listed = round(_sum(soa, "amt") or _sum(soa, "amount"), 2)
        if amt and listed and abs(listed - round(float(amt), 2)) > 1:
            r.blockers.append(
                f"The statement of account lists {len(soa)} row(s) totalling INR {fmt_amount(listed)}, "
                f"but the notice demands INR {fmt_amount(amt)}. One of them is drawn from the wrong "
                f"rows — most often the whole ledger rather than this counterparty's rows."
            )
        # A single dealer's statement does not usually run to dozens of lines.
        # If it does, the ledger was probably never narrowed to this party, and
        # the total will reconcile to itself while still being everyone's.
        if len(soa) > 40:
            r.blockers.append(
                f"The statement of account has {len(soa)} rows. That is far more than one counterparty's "
                f"account normally carries, and suggests the ledger was not narrowed to "
                f"{case.get('noticee_name') or 'this noticee'}. Check the rows belong to this party "
                f"before drafting — other customers' invoices must not appear in this notice."
            )
        who = " ".join(_tokens_of(case.get("noticee_name")))
        if who:
            foreign = []
            for row in soa:
                party = str(row.get("party") or row.get("name") or "").strip()
                if party and not _same_party(party, case.get("noticee_name")):
                    foreign.append(party)
            if foreign:
                r.blockers.append(
                    f"The statement of account contains rows belonging to {len(set(foreign))} other "
                    f"party/parties ({', '.join(sorted(set(foreign))[:3])}…). They must not appear in a "
                    f"notice addressed to {case.get('noticee_name')} — this discloses another customer's "
                    f"data and inflates the demand."
                )

    # ---- 8. read the notice as it will actually print ---------------------
    # Nothing before this ever looked at the finished text — which is how
    # broken sentences, a leftover [● inspection finding] and duplicated
    # paragraphs reached signed notices.
    try:
        blocks, text = draft_blocks, draft_text
        if not blocks:
            _, blocks = DRAFT.build(kind, case, draft_notes)
            text = DRAFT.to_text(kind, case)
        for n in draft_notes:
            add_flag("crit" if n.startswith("Template drift") else "warn", n)
        for l in C.lint(text):
            add_flag("warn", "Read-through: " + l)
        if re.search(r"\b(?:for|of|refund of|reimbursement of|compensation of|pay)\s+\d{4,}\b(?!\s*(?:km|kms|kilomet))",
                     text, re.I):
            add_flag("info", "Some amounts appear without ‘Rs.’/‘INR’ or Indian grouping (e.g. “32000”). "
                             "Write them as “Rs. 32,000/-” in the answers.")
        # read from the document structure: a marker inside a table used to be
        # invisible here, and the notice unlocked as ready to issue
        r.blanks = DRAFT.block_blanks(blocks)
        if r.blanks:
            add_flag("crit", f"{len(r.blanks)} detail(s) are still blank in the notice: "
                             + "; ".join(r.blanks[:8]) + ". A notice with blanks cannot be downloaded as "
                             "ready to issue — fill them, or download it as a marked Fill-in specimen.")
    except Exception as e:                       # the checks must never crash the app
        add_flag("warn", f"The finished-text read-through could not run ({type(e).__name__}: {e}).")

    return r




def _tokens_of(name) -> set:
    import re as _re
    stop = {"the", "and", "ltd", "limited", "pvt", "private", "mr", "mrs", "shri",
            "prop", "proprietor", "company", "messrs", "co"}
    return {w for w in _re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).split()
            if len(w) > 2 and w not in stop}


def _same_party(a, b) -> bool:
    """Substance match, so 'Pvt Ltd' vs 'Private Limited' is not a difference."""
    ta, tb = _tokens_of(a), _tokens_of(b)
    if not ta or not tb:
        return True                      # nothing to compare on — do not cry wolf
    return bool(ta & tb) and len(ta & tb) >= min(2, min(len(ta), len(tb)))


def _days(a, b):
    da, db = parse_date(a), parse_date(b)
    return (db - da).days if da and db else None
