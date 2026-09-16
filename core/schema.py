"""The question set and the field model.

One flat list of questions per notice type, exactly as the console shows them.
`critical` marks the handful of fields a notice cannot assert without —
everything else is optional and renders as [● ...] if left open.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Q:
    id: str
    ask: str
    fills: list[str]                     # field keys this answer supplies
    kind: str = "textarea"               # textarea | text | date | choice | chips | table
    hint: str = ""
    ph: str = ""
    options: list = field(default_factory=list)
    attach: bool = False                 # show the inline uploader
    rows: int = 3
    table: str = ""                      # for kind == "table"


MODES = ["BY SPEED POST",
         "THROUGH SPEED POST / EMAIL / WHATSAPP",
         "BY EMAIL", "BY WHATSAPP", "BY COURIER", "BY HAND DELIVERY"]

# human labels for every field key the app can hold
LABELS = {
    "noticee_type": "Noticee type", "noticee_name": "Noticee name",
    "noticee_address": "Address", "firm_name": "Proprietorship concern",
    "business": "Nature of the company's business", "directors": "Directors",
    "background": "How the dealing arose", "relationship": "How the dealing arose",
    "invoices": "Invoices", "cheques": "Cheque particulars", "soa": "Statement of account",
    "presented_date": "Date presented", "dishonour_date": "Date of dishonour",
    "dishonour_reason": "Reason on the memo", "memo_date": "Bank memo date",
    "part_payment": "Part-payments", "amount": "Amount", "amount_words": "Amount in words",
    "as_on_date": "Outstanding as on", "interest": "Interest rate",
    "principal": "Principal component", "tax": "GST / tax component",
    "jurisdiction": "Place of jurisdiction", "prior": "Prior notice",
    "prior_date": "Prior notice date", "prior_ref": "Prior notice subject",
    "current_instrument": "This notice covers only",
    "mode": "Mode of service", "signatory_name": "Signatory",
    "signatory_desig": "Designation", "authority_confirmed": "Signing authority confirmed",
    "notice_date": "Date of notice", "extra_notes": "Anything else",
    "incoming": "Incoming notice", "advocate_name": "Advocate's name",
    "advocate_address": "Advocate's address", "reply_date": "Date of this reply",
    "client_name": "Client's name", "client_relation": "Client described as",
    "client_address": "Client's address", "product": "Product purchased",
    "dealer": "Dealer / OEM", "claim_date": "Warranty claim received",
    "inspection": "Inspection finding", "rejection": "Disposition communicated",
    "paras": "Para-by-para responses", "demands": "Demands raised",
    "blk_a": "Block A — principal to principal", "blk_b": "Block B — warranty procedure",
    "blk_c": "Block C — no privity",
    "agreement_name": "Agreement title", "agreement_date": "Agreement date",
    "clause_no": "Clause", "obligation": "The obligation", "breach_facts": "Particulars of the breach",
    "cure_period": "Cure period", "consequences": "Consequences if not cured",
    "subject_of": "What the agreement governs", "ground": "Ground",
    "facts": "Facts", "cure_given_date": "Cure period given on",
    "cure_lapsed_date": "Cure period lapsed on", "notice_period": "Notice period",
    "effective_date": "Effective date", "dues": "Outstanding dues",
    "wind_down": "Wind-down obligations", "expiry_date": "Expiry date",
    "intent": "Intent", "renewal_term": "Renewal term", "revised_terms": "Revised terms",
    "confirm_by": "Confirm acceptance by", "direction": "Direction",
    "fm_event": "The event", "fm_date": "Event began on", "affected": "Affected obligations",
    "impact": "Expected impact / duration", "mitigation": "Mitigation steps",
    "relief": "Relief sought", "reason": "Reason for the revision",
    "prices": "Revised prices", "pre_orders": "Orders placed before the effective date",
}

TABLE_COLS = {
    "invoices": [("no", "Invoice no."), ("date", "Date"), ("amt", "Amount (INR)")],
    "cheques":  [("no", "Cheque no."), ("date", "Cheque date"), ("amt", "Amount (INR)"),
                 ("bank", "Drawn on (bank & branch)"),
                 ("dis", "Returned unpaid on"), ("reason", "Return reason"),
                 ("memo", "Bank memo dated")],
    "soa":      [("ref", "Invoice / reference"), ("date", "Document date"), ("amt", "Outstanding (INR)")],
    "prices":   [("sku", "Product / SKU"), ("old", "Existing price"), ("nw", "Revised price"),
                 ("pct", "% change")],
    "directors":[("name", "Director / partner name"), ("address", "Address")],
    "paras":    [("n", "Para"), ("stance", "Stance"), ("text", "Response")],
    "demands":  [("d", "Demand"), ("resp", "Response"), ("note", "Note")],
}
DATE_COLS = {"date", "dis", "memo"}
NUM_COLS = {"amt", "old", "nw"}

# Facts that may be carried per cheque instead of once for the whole notice.
# Several cheques from one drawer rarely bounce on the same day.
CHQ_ROLLUP = {"dis": "dishonour_date", "reason": "dishonour_reason", "memo": "memo_date"}

TYPES = {
    "s138":        dict(name="Section 138 demand notice", blurb="Cheque dishonour", tier="approved"),
    "recovery":    dict(name="Recovery notice", blurb="Outstanding dues, no cheque", tier="approved"),
    "consumer":    dict(name="Reply to a consumer notice", blurb="Inbound consumer notice", tier="approved"),
    "breach":      dict(name="Breach / default notice", blurb="Call to cure", tier="ns"),
    "termination": dict(name="Termination notice", blurb="End an agreement", tier="ns"),
    "renewal":     dict(name="Renewal / non-renewal notice", blurb="Nearing expiry", tier="ns"),
    "fm":          dict(name="Force majeure notice", blurb="Invoke or respond", tier="ns"),
    "price":       dict(name="Price adjustment notice", blurb="Price revision", tier="ns"),
}

# the only fields that stop a notice being drafted
CRITICAL = {
    # The bank memo date is NOT here on purpose: without it the notice simply
    # reads "[● bank memo date]" and the validator computes the statutory window
    # from the return date instead, flagging that it did so. Blocking on it
    # stopped otherwise-complete matters dead. A judgment call — if CEAT's
    # lawyers want it to be a hard stop, add "memo_date" back to this list.
    "s138":        ["noticee_name", "noticee_address", "cheques", "dishonour_date",
                    "dishonour_reason", "amount"],
    "recovery":    ["noticee_name", "noticee_address", "amount", "as_on_date"],
    "consumer":    ["incoming", "advocate_name", "client_name"],
    "breach":      ["noticee_name", "noticee_address", "agreement_name", "clause_no", "breach_facts"],
    "termination": ["noticee_name", "noticee_address", "agreement_name", "clause_no",
                    "ground", "effective_date"],
    "renewal":     ["noticee_name", "noticee_address", "agreement_name", "expiry_date", "intent"],
    "fm":          ["noticee_name", "noticee_address", "agreement_name", "clause_no",
                    "fm_event", "fm_date"],
    "price":       ["noticee_name", "noticee_address", "prices", "effective_date"],
}

_PARTY = [
    Q("party", "Who is the noticee?", ["noticee_type"], kind="choice",
      options=[("Individual / sole proprietor", "Individual / proprietor", "Single addressee block"),
               ("Company + directors", "Company + directors", "Joint & several liability"),
               ("Partnership + partners", "Partnership firm + partners", "Joint & several liability")]),
    Q("addr", "Who is it addressed to — full name(s) and address?",
      ["noticee_name", "noticee_address"], attach=True,
      ph="e.g. M/s Sharma Tyres, Prop. Mr. Rakesh Sharma, Shop 14, MG Road, Jaipur – 302001. "
         "For a company, add the company name and each director's name."),
]
_SEND = [
    Q("mode", "How is it going out?", ["mode"], kind="chips",
      options=[(m, m.title().replace("Whatsapp", "WhatsApp")) for m in MODES]),
    Q("sig", "Who signs it, and are they currently authorised to sign this type?",
      ["signatory_name", "signatory_desig", "authority_confirmed"],
      ph="e.g. Meena Marar, General Manager – Legal — authority confirmed"),
    Q("ndate", "What date should the notice carry?", ["notice_date"], kind="date"),
    Q("extra", "Anything else I should factor in?", ["extra_notes"],
      ph="e.g. prior reminders sent on specific dates, part payments received, "
         "dealership agreement clause numbers, a shorter demand period"),
]
_PRIOR = Q("prior", "Has a notice already gone to this party on this matter?",
           ["prior", "prior_date", "prior_ref", "current_instrument"],
           ph="e.g. no. Or: yes, notice dated 02.05.2026 covering cheque 004401 — this one covers only cheque 004512.")
_JUR = Q("jur", "Where would CEAT file if this isn't resolved?", ["jurisdiction"], kind="text",
         hint="Left blank, the jurisdiction paragraph is left out entirely — never invented.",
         ph="e.g. Mumbai")

QUESTIONS: dict[str, list[Q]] = {
    "s138": _PARTY + [
        Q("dealing", "What is the dealing — how did the relationship arise?", ["background"],
          ph="e.g. Appointed as an authorised dealer in 2022 for supply of tyres in the Jaipur territory."),
        Q("chq", "What are the cheque particulars? Number, date, amount, the bank it was drawn on, and — "
                 "where several cheques bounced on different days — the return date, reason and memo date "
                 "for each.",
          ["cheques"], kind="table", table="cheques", attach=True,
          ph="e.g. Cheque 004512 dated 12.06.2026 for INR 7,50,400 drawn on HDFC Bank Ltd., Sector 14, Gurugram"),
        Q("bounce", "If every cheque bounced the same way, say it once here instead: date presented, "
                    "dishonour date, the exact reason on the memo, and the bank memo date.",
          ["presented_date", "dishonour_date", "dishonour_reason", "memo_date"], attach=True,
          hint="Anything left blank here is taken from the cheque table above, row by row.",
          ph="e.g. Presented 18.06.2026; returned unpaid 20.06.2026 for “Funds Insufficient”; memo dated 20.06.2026"),
        Q("inv", "Which invoices does the cheque cover? Invoice numbers, dates and amounts.",
          ["invoices"], attach=True, ph="Invoice no. | date | amount (INR) — one per line"),
        Q("amt", "Have any part-payments been made since it bounced, and what is the balance now demanded?",
          ["amount", "part_payment"],
          ph="e.g. no part-payments; INR 7,50,400 demanded in full"),
        _JUR, _PRIOR] + _SEND,

    "recovery": _PARTY + [
        Q("dealing", "What is the dealing — how did the relationship arise?", ["relationship"],
          ph="e.g. Appointed as an authorised dealer in 2022 for supply of tyres in the Jaipur territory."),
        Q("soa", "Upload the statement of account or invoice list, or paste the invoice details.",
          ["soa"], attach=True,
          ph="invoice/reference no. | document date | outstanding amount — one per line"),
        Q("total", "What is the total outstanding, and as on what date?", ["amount", "as_on_date"],
          ph="e.g. INR 8,42,150.00 as on 31.08.2026"),
        Q("int", "What interest rate should the notice demand?", ["interest"], kind="chips",
          options=[("8", "8% p.a. (standard)"), ("12", "12% p.a."), ("18", "18% p.a.")]),
        Q("tax", "Is the outstanding tax-inclusive? If so, the principal and the GST split.",
          ["principal", "tax"],
          ph="e.g. principal INR 7,13,686.44 and GST INR 1,28,463.56 — leave blank to omit the paragraph"),
        _JUR, _PRIOR] + _SEND,

    "consumer": [
        Q("incoming", "Paste the incoming consumer notice, or attach it.", ["incoming"],
          attach=True, rows=8,
          hint="The reply is built against this text paragraph by paragraph.",
          ph="Paste the complete notice — every numbered paragraph"),
        Q("who", "Who sent it, and when? Advocate's name, address, and the date on the notice.",
          ["advocate_name", "advocate_address", "notice_date"], attach=True,
          ph="e.g. Adv. S. Krishnan, 22 Law Chambers, Chennai – 600104. Notice dated 04.08.2026."),
        Q("client", "Who is their client, and what did they buy — from whom?",
          ["client_name", "client_relation", "client_address", "product", "dealer"],
          ph="e.g. Mr. A. Kumar, owner of vehicle TN-09-AB-1234, Chennai. Bought from Gill Tyre House, not CEAT."),
        Q("facts", "What are CEAT's own facts? Claim date, inspection finding, what was communicated back.",
          ["claim_date", "inspection", "rejection"], attach=True,
          hint="Leave the finding blank rather than assume one — a blank becomes a VERIFY flag.",
          ph="e.g. claim received 12.05.2026; impact damage, not a manufacturing defect; communicated 20.05.2026"),
        Q("reply", "How should each paragraph be answered?", ["paras"], kind="table", table="paras"),
        Q("demands", "What did they demand, and is any of it conceded?", ["demands"],
          kind="table", table="demands"),
        Q("rdate", "What date should the reply carry?", ["reply_date"], kind="date"),
    ] + _SEND[1:],

    "breach": _PARTY + [
        Q("agr", "Which agreement, and which clause has been breached?",
          ["agreement_name", "agreement_date", "clause_no"], attach=True,
          hint="Attach the agreement rather than citing a clause number from memory.",
          ph="e.g. Dealership Agreement dated 04.03.2025; Clause 7.2 (minimum offtake and payment terms)"),
        Q("oblig", "What did that clause require them to do?", ["obligation"],
          ph="e.g. lift a minimum of 400 tyres per quarter and settle invoices within 30 days"),
        Q("facts", "What actually happened — the factual particulars of the breach?",
          ["breach_facts"], attach=True,
          ph="e.g. no orders since 14.02.2026 and January invoices unpaid despite reminders"),
        Q("cure", "How long should they get to cure it?", ["cure_period"], kind="chips",
          options=[("7 (SEVEN) days", "7 days"), ("15 (FIFTEEN) days", "15 days"),
                   ("30 (THIRTY) days", "30 days")]),
        Q("conseq", "What happens if they don't?", ["consequences"],
          ph="e.g. terminate the Agreement and initiate proceedings for recovery of dues and losses"),
        _PRIOR] + _SEND,

    "termination": _PARTY + [
        Q("agr", "Which agreement is being terminated, what does it govern, and under which clause?",
          ["agreement_name", "agreement_date", "subject_of", "clause_no"], attach=True,
          ph="e.g. Dealership Agreement dated 04.03.2025 governing supply in Jaipur; terminable under Clause 12.1"),
        Q("ground", "On what ground?", ["ground"], kind="chips",
          options=[("Breach", "Breach"), ("Convenience", "Convenience"), ("Expiry", "Expiry of term")]),
        Q("detail", "The detail: for a breach, what was required and what happened, with the cure dates. "
                    "Otherwise the notice period.",
          ["obligation", "facts", "cure_given_date", "cure_lapsed_date", "notice_period"],
          ph="e.g. required to clear dues within 30 days; cure notice 02.06.2026, lapsed 17.06.2026, still unpaid"),
        Q("eff", "Effective from what date?", ["effective_date"], kind="date"),
        Q("wind", "What must they do on the way out — dues, stock, signage?", ["wind_down", "dues"],
          ph="e.g. clear dues of INR 3,20,000, return Company property and stock, cease use of CEAT marks"),
        _PRIOR] + _SEND,

    "renewal": _PARTY + [
        Q("agr", "Which agreement, when does it expire, and which clause governs renewal?",
          ["agreement_name", "agreement_date", "expiry_date", "clause_no"], attach=True,
          ph="e.g. Dealership Agreement dated 04.03.2023, expiring 03.03.2027; Clause 3.2, 60 days' notice"),
        Q("intent", "Renewing, or not?", ["intent"], kind="chips",
          options=[("Renew", "Renew"), ("Do not renew", "Do not renew")]),
        Q("terms", "On what terms, and by when should they confirm? If not renewing, what must they wind down?",
          ["renewal_term", "revised_terms", "confirm_by", "wind_down", "notice_period"],
          ph="e.g. a further term of 2 years on existing terms; confirm by 01.02.2027"),
    ] + _SEND,

    "fm": _PARTY + [
        Q("agr", "Which agreement, and which force majeure clause?",
          ["agreement_name", "agreement_date", "clause_no", "direction"], attach=True,
          ph="e.g. Supply Agreement dated 11.09.2024; force majeure at Clause 14. CEAT is invoking it."),
        Q("event", "What happened, and when did it start?", ["fm_event", "fm_date"], attach=True,
          ph="e.g. flooding at the Nashik facility from 10.08.2026 following an evacuation order"),
        Q("impact", "What can't be performed, for how long, and what is being done about it?",
          ["affected", "impact", "mitigation"],
          ph="e.g. despatches suspended; 6–8 weeks; production shifting to Halol"),
        Q("relief", "What are you asking them to do?", ["relief"],
          ph="e.g. extend the delivery timelines accordingly"),
    ] + _SEND,

    "price": _PARTY + [
        Q("basis", "Under what arrangement, and why is the price changing?",
          ["agreement_name", "agreement_date", "clause_no", "reason"], attach=True,
          ph="e.g. Dealership Agreement dated 04.03.2025, Clause 9.3; movement in raw-material costs"),
        Q("prices", "What are the revised prices? Upload the price list, or list them.",
          ["prices"], attach=True,
          ph="product / SKU | existing price | revised price | % change"),
        Q("eff", "Effective from what date?", ["effective_date"], kind="date"),
        Q("pre", "What happens to orders already placed before that date?", ["pre_orders"],
          ph="e.g. honoured at existing prices provided despatch is taken within 30 days"),
    ] + _SEND,
}


def label(key: str) -> str:
    return LABELS.get(key, key.replace("_", " ").capitalize())


def questions(kind: str) -> list[Q]:
    return QUESTIONS.get(kind, [])


def critical(kind: str) -> list[str]:
    return CRITICAL.get(kind, [])


def is_filled(case: dict, key: str) -> bool:
    v = case.get(key)
    if isinstance(v, list):
        return len(v) > 0
    return v is not None and str(v).strip() != ""


def rows(case: dict, key: str) -> list[dict]:
    """Table rows for `key`, whatever junk is actually in the slot.

    A table field can briefly hold a raw string (typed into a free-text box
    before analysis turns it into rows), and nothing downstream should crash
    on that — it just means no rows yet.
    """
    v = case.get(key)
    return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []


def effective(kind: str, case: dict) -> dict:
    """A read-only view of the case in which a dishonour fact recorded against
    every cheque counts as known, even if the single free-text answer is empty.

    Without this, three cheques each carrying their own return date would still
    read as “bank memo date missing” and block the draft.
    """
    if kind != "s138":
        return case
    chq = rows(case, "cheques")
    if not chq:
        return case
    out = dict(case)
    for col, key in CHQ_ROLLUP.items():
        vals = [str(r.get(col, "")).strip() for r in chq]
        if not all(vals):
            continue
        uniq = list(dict.fromkeys(vals))
        out[f"_{key}_perrow"] = True
        out[f"_{key}_uniform"] = len(uniq) == 1
        if not str(out.get(key, "")).strip():
            out[key] = uniq[0] if len(uniq) == 1 else "; ".join(uniq)
    return out
