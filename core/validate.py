"""The checks that run before anything is drafted.

Two layers, deliberately: the model is asked not to invent, and then everything
it returned is re-checked here against arithmetic, dates and the notice type's
own mandatory checklist. A blocker stops the draft; a flag travels with it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import skill_loader as SK
from .config import MAX_DOC_CHARS, MAX_SHEET_ROWS
from .schema import CRITICAL, TABLE_COLS, effective, is_filled, label, rows
from .words import fmt_amount, fmt_date, parse_date, to_float, to_words, words_key


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

    @property
    def ok(self) -> bool:
        return not self.blockers


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
        add_flag("warn", SK.nonstandard_warning())

    # ---- 3. standing checks ---------------------------------------------
    if not case.get("authority_confirmed"):
        who = case.get("signatory_name") or "the named signatory"
        add_flag("warn", f"Signing authority not confirmed — check that {who} is currently "
                         f"authorised to sign this notice type.")
    if str(case.get("prior", "")).lower().startswith("don"):
        add_flag("warn", "VERIFY: check for prior notices to this counterparty on this matter.")
    elif str(case.get("prior", "")).lower().startswith("y"):
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
        if chq_total and amt and abs(chq_total - amt) > 0.5:
            explained = bool(str(case.get("part_payment", "")).strip())
            add_flag("warn" if explained else "crit",
                     f"Demanded amount (INR {fmt_amount(amt)}) does not equal the cheque total "
                     f"(INR {fmt_amount(chq_total)})."
                     + (" A part-payment paragraph is present — confirm the arithmetic."
                        if explained else " Record the part-payments, or correct the figure."))
            if not explained:
                r.blockers.append("The demand does not tie to the cheque total, and no part-payment "
                                  "is recorded to explain it.")
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
        chk("pass", "Subject cites Section 138 r/w Section 141, NI Act, 1881.")
        chk("pass", "Demand gives 15 (FIFTEEN) days from receipt.")
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
        chk("pass", "Demand gives 10 days from receipt; civil and criminal language present.")

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

    # ---- 5. figures and words must agree ---------------------------------
    # Compared on the number words alone: a missing "Rupees" prefix or "Only"
    # is a formatting difference that house_words() fixes at draft time, not a
    # mismatch between the figure and the words.
    if amt and str(case.get("amount_words", "")).strip():
        if words_key(case["amount_words"]) != words_key(to_words(amt)):
            r.blockers.append(f"The amount in words does not match the figure. INR {fmt_amount(amt)} reads "
                              f"as “{to_words(amt)}”, but the notice would say “{case['amount_words']}”.")

    chk("pass", "Every output carries the review banner and is a draft for legal review.")

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
        listed = round(_sum(soa, "amount"), 2)
        if amt and listed and abs(listed - round(float(amt), 2)) > 1:
            r.blockers.append(
                f"The statement of account lists {len(soa)} row(s) totalling INR {fmt_amount(listed)}, "
                f"but the notice demands INR {fmt_amount(amt)}. One of them is drawn from the wrong "
                f"rows — most often the whole ledger rather than this counterparty's rows."
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
