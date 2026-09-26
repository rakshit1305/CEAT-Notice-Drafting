"""The question set and the field model.

One flat list of questions per notice type, exactly as the console shows them.
`critical` marks the handful of fields a notice cannot assert without —
everything else is optional and renders as [● ...] if left open.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from .words import find_amounts, to_float


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
    "part_payment": "Part-payments", "part_paid": "Part-payment received (INR)",
    "part_paid_date": "Part-payment date", "amount": "Amount", "amount_words": "Amount in words",
    "as_on_date": "Outstanding as on", "interest": "Interest rate",
    "interest_from": "Interest runs from",
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
    "dealer": "Dealer / OEM", "dealer_authorised": "Bought from an authorised CEAT dealer?",
    "claim_date": "Warranty claim received",
    "inspection": "Inspection finding", "rejection": "Disposition communicated",
    "paras": "Para-by-para responses", "demands": "Demands raised",
    "blk_a": "Block A — principal to principal", "blk_b": "Block B — warranty procedure",
    "blk_c": "Block C — no privity",
    "agreement_name": "Agreement title", "agreement_date": "Agreement date",
    "clause_no": "Clause", "obligation_clause": "Clause containing the obligation",
    "attn_name": "Kind attention", "attn_desig": "Designation (kind attention)",
    "email": "Email address", "notice_ref": "Their notice reference",
    "deposit_held": "Security deposit held", "effect_on_receipt": "Takes effect on receipt",
    "fm_continue": "If the event continues", "obligation": "The obligation", "breach_facts": "Particulars of the breach",
    "cure_period": "Cure period", "consequences": "Consequences if not cured",
    "subject_of": "What the agreement governs", "ground": "Ground",
    "facts": "Facts", "cure_given_date": "Cure period given on",
    "cure_lapsed_date": "Cure period lapsed on", "notice_period": "Notice period",
    "effective_date": "Effective date", "price_change_pct": "Overall % change", "dues": "Outstanding dues",
    "wind_down": "Wind-down obligations", "expiry_date": "Expiry date",
    "intent": "Intent", "renewal_term": "Renewal term", "revised_terms": "Revised terms",
    "confirm_by": "Confirm acceptance by", "direction": "Direction",
    "fm_event": "The event", "fm_date": "Event began on", "affected": "Affected obligations",
    "impact": "Expected impact / duration", "mitigation": "Mitigation steps",
    "relief": "Relief sought", "reason": "Reason for the revision",
    "prices": "Revised prices", "quantities": "Affected quantities",
    "schedule": "Schedule of particulars", "pre_orders": "Orders placed before the effective date",
}

# What each field MEANS. The model used to receive bare keys such as
# "client_name" and had to guess — it once put CEAT itself into the consumer's
# slot. These definitions go into the analysis prompt verbatim.
FIELD_HELP = {
    "noticee_name": "the party the notice is addressed to (never CEAT). For a sole proprietorship, "
                    "the proprietor's own name — the individual, not only the firm name",
    "firm_name": "the proprietorship firm's trading name, e.g. 'M/s Sharma Tyres'",
    "noticee_address": "the noticee's postal address",
    "business": "the noticee's line of business as a phrase, e.g. 'the business of purchase and sale "
                "of tyres' — not the relationship history",
    "background": "how the dealing between CEAT and the noticee arose (dealership, since when, terms). "
                  "Not the invoice or cheque particulars",
    "relationship": "how the dealing between CEAT and the noticee arose",
    "amount": "Section 138: the amount demanded = total of the dishonoured cheque(s) minus any "
              "part-payment received AFTER dishonour; never the invoice total. Recovery: the total "
              "outstanding. Digits only",
    "part_payment": "a description of payments received after the cheque bounced. Leave empty if "
                    "none were received",
    "part_paid": "the total amount received after the cheque bounced, digits only; 0 if none",
    "part_paid_date": "date of that part-payment",
    "as_on_date": "the date the outstanding balance is stated as on",
    "interest_from": "when interest starts, e.g. 'from the due date of each invoice'",
    "client_name": "consumer reply: the CONSUMER on whose behalf the incoming notice was sent — the "
                   "advocate's client. NEVER CEAT Limited, which is the recipient of that notice",
    "client_relation": "consumer reply: how the consumer describes himself/herself, e.g. 'owner of "
                       "vehicle GJ-01-RK-4567'",
    "client_address": "consumer reply: the CONSUMER's address as given in the incoming notice — never "
                      "CEAT's address",
    "advocate_name": "consumer reply: the advocate who signed the incoming notice",
    "advocate_address": "consumer reply: that advocate's office address",
    "notice_date": "consumer reply: the date printed on the INCOMING notice. Every other type: the "
                   "date this notice will carry",
    "reply_date": "consumer reply: the date CEAT's reply will carry",
    "dealer": "consumer reply: the dealer/OEM the consumer bought from",
    "dealer_authorised": "consumer reply: 'Yes' if that dealer is an authorised CEAT dealer, 'No' if "
                         "not, 'Not sure' otherwise",
    "claim_date": "consumer reply: the date CEAT received the warranty claim, only if CEAT's own "
                  "records show one",
    "inspection": "consumer reply: CEAT's inspection finding, only if an inspection happened",
    "price_change_pct": "price notice: the overall percentage revision, when no SKU-wise table is given",
    "quantities": "force majeure: the affected deliveries — one row per month/period with scheduled, "
                  "delivered, pending and the due date",
    "email": "the recipient's email address, if the notice is also being sent by email",
    "notice_ref": "consumer reply: the reference number printed on the incoming notice",
    "deposit_held": "termination: the security deposit the Company holds, digits only",
    "schedule": "the item-by-item particulars behind the breach — one row per claim, invoice or "
                "transaction, with its reference, date, amount and what was found",
    "effect_on_receipt": "termination: 'Yes' if termination takes effect on receipt of the notice "
                         "rather than on a fixed date",
    "fm_continue": "force majeure: what happens if the event continues beyond a stated period",
    "obligation_clause": "termination: the clause that imposed the obligation breached — usually NOT "
                         "the termination clause, which is clause_no",
    "attn_name": "a contact person the notice is marked for the attention of. NOT a noticee: use this "
                 "for a manager or director named only as a contact, e.g. in a force majeure, renewal "
                 "or price notice",
    "attn_desig": "that contact person's designation",
    "obligation": "breach: what the clause required the other party to do",
    "breach_facts": "breach: what actually happened — the particulars of the breach",
    "consequences": "breach: what CEAT will do if the breach is not cured",
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
    "quantities": [("period", "Month / period"), ("sched", "Scheduled"), ("done", "Delivered"),
                   ("pend", "Pending"), ("due", "Due date")],
    "schedule": [("ref", "Reference"), ("date", "Date"), ("amt", "Amount (INR)"),
                 ("finding", "Finding / remark")],
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
    "consumer":    ["incoming", "advocate_name", "client_name", "notice_date"],
    "breach":      ["noticee_name", "noticee_address", "agreement_name", "clause_no", "breach_facts"],
    "termination": ["noticee_name", "noticee_address", "agreement_name", "clause_no",
                    "ground", "effective_date"],
    "renewal":     ["noticee_name", "noticee_address", "agreement_name", "expiry_date", "intent"],
    "fm":          ["noticee_name", "noticee_address", "agreement_name", "clause_no",
                    "fm_event", "fm_date"],
    # "prices" is not listed here: a price notice may state a SKU-wise table OR
    # an overall percentage. validate.py requires one of the two.
    "price":       ["noticee_name", "noticee_address", "effective_date"],
}

_PARTY = [
    Q("party", "Who is the noticee?", ["noticee_type"], kind="choice",
      options=[("Individual / sole proprietor", "Individual / proprietor", "Single addressee block"),
               ("Company + directors", "Company + directors", "Joint & several liability"),
               ("Partnership + partners", "Partnership firm + partners", "Joint & several liability")]),
    Q("addr", "Who is it addressed to — full name(s) and address?",
      ["noticee_name", "noticee_address", "attn_name", "attn_desig", "email"], attach=True,
      hint="For a sole proprietorship, give the proprietor's own name as well as the firm — a "
           "proprietorship is not a separate legal person.",
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
          ["amount", "part_payment", "part_paid", "part_paid_date"],
          hint="The demand in a cheque notice is the cheque amount less any payment received after "
               "it bounced — never the invoice total. State any payment as an amount and a date.",
          ph="e.g. no part-payments; INR 7,50,400 demanded in full. "
             "Or: INR 50,000 received on 25.06.2026; balance INR 7,00,400 demanded."),
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
        Q("int_from", "From when does interest run?", ["interest_from"], kind="chips",
          options=[("from the due date of each invoice", "Due date of each invoice"),
                   ("from the date of this notice", "Date of this notice"),
                   ("from the as-on date stated above", "The as-on date")],
          hint="Without a start date the interest demand cannot be worked out."),
        Q("tax", "Is the outstanding tax-inclusive? If so, the principal and the GST split.",
          ["principal", "tax"],
          ph="e.g. principal INR 7,13,686.44 and GST INR 1,28,463.56 — leave blank to omit the paragraph"),
        _JUR, _PRIOR] + _SEND,

    "consumer": [
        Q("incoming", "Paste the incoming consumer notice, or attach it.", ["incoming"],
          attach=True, rows=8,
          hint="The reply is built against this text paragraph by paragraph.",
          ph="Paste the complete notice — every numbered paragraph"),
        Q("who", "Who sent it, and when? Advocate's name, address, the date and any reference number.",
          ["advocate_name", "advocate_address", "notice_date", "notice_ref", "email"], attach=True,
          ph="e.g. Adv. S. Krishnan, 22 Law Chambers, Chennai – 600104. Notice dated 04.08.2026."),
        Q("client", "Who is their client, and what did they buy — from whom?",
          ["client_name", "client_relation", "client_address", "product", "dealer"],
          ph="e.g. Mr. A. Kumar, owner of vehicle TN-09-AB-1234, Chennai. Bought from Gill Tyre House, not CEAT."),
        Q("dealer_auth", "Is that dealer an authorised CEAT dealer?", ["dealer_authorised"], kind="chips",
          options=[("Yes", "Yes — authorised CEAT dealer"), ("No", "No — not our dealer / an OEM"),
                   ("Not sure", "Not sure")],
          hint="This decides the no-privity paragraph. Saying the purchase was not from an authorised "
               "dealer when it was would be a false statement in a signed reply."),
        Q("facts", "What are CEAT's own facts? Claim date, inspection finding, what was communicated back.",
          ["claim_date", "inspection", "rejection"], attach=True,
          hint="Leave the finding blank rather than assume one — a blank becomes a VERIFY flag.",
          ph="e.g. claim received 12.05.2026; impact damage, not a manufacturing defect; communicated 20.05.2026"),
        Q("reply", "How should each paragraph be answered?", ["paras"], kind="table", table="paras"),
        Q("demands", "What did they demand, and is any of it conceded?", ["demands"],
          kind="table", table="demands"),
        Q("rdate", "What date should the reply carry?", ["reply_date"], kind="date"),
        # Not _SEND[1:]: that includes "What date should the notice carry?", which
        # for a reply wrote TODAY into notice_date — the field the "Re: Your Notice
        # dated …" line reads — so replies cited the incoming notice as dated today.
    ] + [_SEND[1], _SEND[3]],

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
          ["obligation", "obligation_clause", "facts", "cure_given_date", "cure_lapsed_date",
           "notice_period"],
          hint="Name the clause that imposed the obligation — it is usually NOT the termination clause "
               "given above. Writing 'under Clause 7.2' here keeps the two apart in the notice.",
          ph="e.g. under Clause 7.2, required to clear dues within 30 days; cure notice 02.06.2026, "
             "lapsed 17.06.2026, still unpaid"),
        Q("eff", "Effective from what date?", ["effective_date"], kind="date"),
        Q("sched", "The particulars, item by item, if you have them", ["schedule"], attach=True,
          hint="One line per claim or invoice: reference | date | amount | what was found. These "
               "are the evidence for the notice and are annexed as a Schedule.",
          ph="CLM/2026/0412 | 14.02.2026 | 12,300 | serial number buffed and re-embossed"),
        Q("deposit", "Do you hold a security deposit, and does termination take effect on receipt?",
          ["deposit_held", "effect_on_receipt"],
          hint="Most agreements make termination effective when the notice is received, not on a "
               "date you choose.",
          ph="e.g. security deposit of INR 1,00,000 held; termination to take effect on receipt"),
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
        Q("qty", "The affected quantities, if they can be listed", ["quantities"], attach=True,
          hint="One line per month or delivery: period | scheduled | delivered | pending | due "
               "date. A table is far harder to dispute later than the same figures in a sentence.",
          ph="September 2026 | 400 | 160 | 240 | 25.09.2026"),
        Q("cont", "What happens if the event continues?", ["fm_continue"],
          hint="Most force majeure clauses let either side terminate or renegotiate if the event "
               "runs beyond a stated period.",
          ph="e.g. if it continues beyond 60 days, either party may terminate on 15 days' notice "
             "under Clause 14.4"),
        Q("relief", "What are you asking them to do?", ["relief"],
          ph="e.g. extend the delivery timelines accordingly"),
    ] + _SEND,

    "price": _PARTY + [
        Q("basis", "Under what arrangement, and why is the price changing?",
          ["agreement_name", "agreement_date", "clause_no", "reason"], attach=True,
          ph="e.g. Dealership Agreement dated 04.03.2025, Clause 9.3; movement in raw-material costs"),
        Q("prices", "What are the revised prices? Upload the price list, or list them.",
          ["prices", "price_change_pct"], attach=True,
          hint="One line per product: SKU | existing price | revised price | % change. If only an "
               "overall percentage has been agreed, state that instead.",
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


_NO_PART = re.compile(r"\b(?:no|none|nil|not|without any)\b[^.]{0,30}(?:part[- ]?pay|payment)", re.I)


def part_paid(case: dict):
    """Money received against the dishonoured cheque(s) after dishonour.

    0.0 when none was received (or the answer says so), the amount when it is
    stated, and None when a part-payment is described but no figure is given —
    which the validator treats as a gap, never as zero.
    """
    v = case.get("part_paid")
    if str(v if v is not None else "").strip() != "":
        f = to_float(v)
        if f is not None:
            return f
    t = str(case.get("part_payment") or "").strip()
    if not t or _NO_PART.search(t):
        return 0.0
    m = re.search(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)[^.;\n]{0,40}?\b(?:received|paid)", t, re.I) \
        or re.search(r"\b(?:received|paid|part[- ]?payment of)\b[^\d.;\n]{0,20}(?:INR|Rs\.?|₹)\s*"
                     r"([\d,]+(?:\.\d{1,2})?)", t, re.I)
    return to_float(m.group(1)) if m else None
