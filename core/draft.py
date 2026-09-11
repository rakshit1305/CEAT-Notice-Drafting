"""Assemble the notice from CEAT's approved wording, and write the .docx.

Every paragraph here is the skill's template wording. Only the bracketed facts
vary. Anything unsupplied renders as [● label] — never a guess.
"""
from __future__ import annotations
import io
from dataclasses import dataclass, field

from . import skill_loader as SK
from .config import blank
from .schema import label, rows
from .words import fmt_amount, fmt_date, inr, to_float, to_words

MODES_DEFAULT = "BY SPEED POST"


# --------------------------------------------------------------------------
# a tiny document model: paragraphs, numbered lists and tables
# --------------------------------------------------------------------------
@dataclass
class Block:
    kind: str                  # p | ol | table | stamp | addr | sig | subject | re
    text: str = ""
    items: list = field(default_factory=list)
    head: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    bold: bool = False
    underline: bool = False


def V(case, key, lbl=None):
    v = case.get(key)
    if v is None or str(v).strip() == "":
        return blank(lbl or label(key).lower())
    return str(v).strip()


def D(case, key, lbl=None):
    v = case.get(key)
    s = fmt_date(v) if v else ""
    return s or blank(lbl or label(key).lower())


def M(case, key, lbl=None):
    v = to_float(case.get(key))
    return inr(v) if v is not None else blank(lbl or label(key).lower())


def W(case, key="amount", lbl="amount in words"):
    typed = str(case.get("amount_words") or "").strip()
    if typed:
        return typed
    v = to_float(case.get(key))
    return to_words(v) if v is not None else blank(lbl)


def chq_facts(case, chq):
    """Per-cheque (no, returned-on, reason, memo date), each falling back to the
    single answer given for the whole notice. Uniform means one sentence will do."""
    rows = []
    for c in chq:
        rows.append((
            str(c.get("no", "")).strip(),
            str(c.get("dis", "")).strip() or str(case.get("dishonour_date", "")).strip(),
            str(c.get("reason", "")).strip() or str(case.get("dishonour_reason", "")).strip(),
            str(c.get("memo", "")).strip() or str(case.get("memo_date", "")).strip(),
        ))
    return rows, len({r[1:] for r in rows}) <= 1


def noticee_block(case) -> str:
    lines = []
    if str(case.get("noticee_type", "")).startswith("Company"):
        lines += ["Noticee No. 1", V(case, "noticee_name"), V(case, "noticee_address")]
        for i, d in enumerate(rows(case, "directors"), start=2):
            if str(d.get("name", "")).strip():
                lines += ["", f"Noticee No. {i}", d["name"]]
                if str(d.get("address", "")).strip():
                    lines.append(d["address"])
    else:
        lines.append(V(case, "noticee_name"))
        if str(case.get("firm_name", "")).strip():
            lines.append("Proprietor, " + case["firm_name"])
        lines.append(V(case, "noticee_address"))
    return "\n".join(lines)


def you(case) -> str:
    return ("you Noticees, jointly and severally,"
            if str(case.get("noticee_type", "")).startswith("Company") else "you")


def sig_block(case) -> str:
    return ("Yours faithfully,\nFor CEAT Limited\n\n\n_________________\n"
            + V(case, "signatory_name") + "\n" + V(case, "signatory_desig"))


# --------------------------------------------------------------------------
def build(kind: str, case: dict) -> tuple[str, list[Block]]:
    ro = SK.reg_office()
    blocks: list[Block] = []
    subject = ""

    if kind == "consumer":
        blocks.append(Block("addr", text="To,\n" + V(case, "advocate_name", "advocate") + ", Advocate\n"
                                          + V(case, "advocate_address", "advocate's address")))
        blocks.append(Block("p", text=D(case, "reply_date", "date of this reply")))
        blocks.append(Block("re", text="Re: Your Notice dated " + D(case, "notice_date") + " (“Said Notice”)"))
        subject = "Reply to your Said Notice."
    else:
        blocks.append(Block("p", text=D(case, "notice_date")))
        blocks.append(Block("stamp", text=case.get("mode") or MODES_DEFAULT, bold=True))
        blocks.append(Block("stamp", text="WITHOUT PREJUDICE", bold=True, underline=True))
        blocks.append(Block("addr", text="To,\n" + noticee_block(case)))

    li: list = []

    if kind == "s138":
        subject = "Legal Notice u/s 138 r/w Section 141 of the Negotiable Instruments Act, 1881."
        opening = (f"We, CEAT Limited, having our Registered Office at {ro}, "
                   "serve upon you the following notice:")
        li.append("That we are a Public Limited Company duly registered under the provisions of the "
                  "Companies Act, 1956, having our registered office at the address mentioned above. "
                  "We deal in the business of manufacture and sale of Tyres, Tubes and Flaps "
                  "(hereinafter referred to as the “Goods”).")
        if str(case.get("noticee_type", "")).startswith("Company"):
            dirs = [d.get("name", "") for d in rows(case, "directors") if d.get("name")]
            li.append(f"That you Noticee No. 1, {V(case,'noticee_name')}, are a company registered in India "
                      f"engaged in {V(case,'business','nature of business')}; and "
                      f"{'Noticee Nos. 2 and 3, ' + ' and '.join(dirs) if dirs else blank('director names')}, "
                      "are its directors responsible for its management and day-to-day operations.")
        else:
            li.append("That you are the sole proprietor and the person in control and management of the "
                      f"proprietorship concern {V(case,'firm_name','firm name')}, having your office and "
                      f"residential address at {V(case,'noticee_address')}, engaged in the business of "
                      "purchase and sale of Goods.")
        li.append(V(case, "background", "how the dealing arose"))
        li.append("That in the course of business and against orders placed by you, the Company sold, "
                  "supplied and delivered the said Goods from time to time as per your requirements, which "
                  "were duly received, acknowledged and accepted by you without demur as to quality "
                  "and/or quantity.")
        inv = rows(case, "invoices")
        if inv:
            li.append(("That the Company supplied Goods vide the following invoice(s), received by you "
                       "without complaint, against which you are liable to make payment:",
                       dict(head=["Invoice No.", "Invoice Date", "Amount (INR)"],
                            rows=[[r.get("no", "—"), fmt_date(r.get("date")) or "—",
                                   fmt_amount(r.get("amt")) or "—"] for r in inv])))
        else:
            li.append("That the Company supplied Goods vide invoices received by you without complaint, "
                      "against which you are liable to make payment: " + blank("invoice particulars"))
        chq = rows(case, "cheques")
        if len(chq) > 1:
            li.append(("That in discharge of your admitted liability you issued the following cheques:",
                       dict(head=["Cheque No.", "Cheque Date", "Amount (INR)", "Drawn on"],
                            rows=[[c.get("no", "—"), fmt_date(c.get("date")) or "—",
                                   fmt_amount(c.get("amt")) or "—", c.get("bank", "—")] for c in chq])))
        else:
            c = chq[0] if chq else {}
            li.append("That in discharge of your admitted liability you issued cheque no. "
                      f"{c.get('no') or blank('cheque no.')} dated "
                      f"{fmt_date(c.get('date')) or blank('cheque date')} for INR "
                      f"{fmt_amount(c.get('amt')) or blank('cheque amount')}/- drawn on "
                      f"{c.get('bank') or blank('drawn-on bank')}.")
        facts, uniform = chq_facts(case, chq)
        if len(facts) > 1 and not uniform:
            li.append(("That the aforesaid cheques were presented for clearance and, to our shock, "
                       "were returned unpaid by the drawee bank, as follows:",
                       dict(head=["Cheque No.", "Returned unpaid on", "Reason", "Bank memo dated"],
                            rows=[[n or "—",
                                   fmt_date(d) or blank("date of dishonour"),
                                   f"“{r}”" if r else blank("reason on memo"),
                                   fmt_date(m) or blank("bank memo date")]
                                  for n, d, r, m in facts])))
        else:
            if facts:
                _, d0, r0, m0 = facts[0]
            else:
                d0 = str(case.get("dishonour_date", "")).strip()
                r0 = str(case.get("dishonour_reason", "")).strip()
                m0 = str(case.get("memo_date", "")).strip()
            plural = "cheques were" if len(facts) > 1 else "cheque(s) was/were"
            li.append(f"That the aforesaid {plural} presented for clearance and, to our shock, "
                      f"returned unpaid on {fmt_date(d0) or blank('date of dishonour')} for the reason "
                      f"“{r0 or blank('reason on memo')}” vide bank memo dated "
                      f"{fmt_date(m0) or blank('bank memo date')}.")
        if str(case.get("part_payment", "")).strip():
            li.append(str(case["part_payment"]).strip())
        many = len(chq) > 1
        cs = "cheques" if many else "cheque(s)"
        it = "they" if many else "it/they"
        li.append("That despite our repeated efforts to contact you for payment of the balance amount "
                  f"against the dishonoured {cs}, you have failed and neglected to pay, demonstrating "
                  "your disregard for the consequences of non-payment.")
        li.append("That your conduct reveals an intention tainted with fraud. Prima facie you deliberately "
                  f"issued the aforesaid {cs} with knowledge that {it} would be dishonoured, thereby "
                  "not only committing an offence under Section 138 of the Negotiable Instruments Act, 1881, "
                  "but also criminal breach of trust punishable under Section 316(2) of the Bharatiya Nyaya "
                  "Sanhita, 2023 (“BNS”), and cheating under Section 318(4) of the BNS.")
        li.append(f"Hence, through this notice, {you(case)} are called upon to remit to the Company the "
                  f"entire legally enforceable debt of {M(case,'amount','amount demanded')} ({W(case)}) "
                  f"against the dishonoured {cs}, within a period of 15 (FIFTEEN) days from the date of "
                  "receipt of this notice, failing which the Company shall be constrained to initiate "
                  "appropriate legal proceedings against you, for which you shall be solely responsible for "
                  "the costs and consequences arising therefrom.")
        tail = ["Please note that a copy of this notice has been retained by us for future reference."]

    elif kind == "recovery":
        rate = str(case.get("interest") or "8").strip()
        subject = (f"Demand notice for recovery of dues amounting to {M(case,'amount')} ({W(case)}) "
                   f"along with interest @ {rate}% p.a.")
        opening = None
        li.append("CEAT Limited (“the Company”) is a Public Limited Company duly incorporated under the "
                  f"provisions of the Companies Act, 1956, having its Registered Office at {ro}.")
        li.append("The Company deals in the business of manufacture and sale of Tyres, Tubes and Flaps "
                  "(hereinafter referred to as the “Said Materials”).")
        li.append(V(case, "relationship", "how the dealing arose"))
        li.append("That in the course of business and against orders placed by you, the Company sold, "
                  "supplied and delivered the Said Materials from time to time, duly received, acknowledged "
                  "and accepted by you without demur as to quality and/or quantity.")
        li.append("Towards the supply, the Company raised various invoices and maintained a running and "
                  "continuous account of your transactions reflecting the amounts due and payable.")
        li.append("The Said Materials were received by you in full satisfaction, and you were liable to pay "
                  "the invoice amounts, the Company having supplied on the assurance of payment within 30 "
                  "days from the date of invoice. However, you have failed to pay the outstanding invoices.")
        soa = rows(case, "soa")
        p7 = (f"As per the Company's records, as on {D(case,'as_on_date','as-on date')} a total outstanding "
              f"amount of {M(case,'amount','outstanding amount')} ({W(case)}) is pending from you towards "
              "the Said Materials supplied.")
        if soa:
            total = sum(to_float(r.get("amt")) or 0 for r in soa)
            li.append((p7 + " The Statement of Account is as follows:",
                       dict(head=["SR No.", "Invoice / Reference", "Document Date", "Outstanding (INR)"],
                            rows=[[str(i), r.get("ref", "—"), fmt_date(r.get("date")) or "—",
                                   fmt_amount(r.get("amt")) or "—"] for i, r in enumerate(soa, 1)]
                                 + [["", "Total", "", fmt_amount(total)]])))
        else:
            li.append(p7)
        li.append("Despite the Company's vigorous follow-ups, you have failed to make payment as per the "
                  "agreed terms and conditions.")
        li.append(f"As per the agreed terms of the invoices, {you(case)} are liable and duty-bound to pay "
                  f"the outstanding amount of {M(case,'amount','outstanding amount')} ({W(case)}) as on "
                  f"{D(case,'as_on_date','as-on date')}.")
        if str(case.get("principal", "")).strip() or str(case.get("tax", "")).strip():
            li.append(f"The aforesaid outstanding amount of {M(case,'amount')} comprises a principal sum of "
                      f"{M(case,'principal','principal')} and applicable GST/tax of {M(case,'tax','tax component')}, "
                      "as reflected in the invoices referred to above.")
        li.append("You received the Said Materials as per your requirement and yet failed to pay, "
                  "demonstrating a false and fraudulent intention from the beginning. Your acts and conduct "
                  "are patently illegal, untenable and contrary to settled principles of law.")
        li.append("In the aforesaid circumstances, the Company hereby calls upon you to pay the aforesaid "
                  f"sum of {M(case,'amount')} ({W(case)}) along with interest @ {rate}% p.a.")
        li.append("Through your deliberate and wilful actions you have deceived and cheated the Company, "
                  "attracting the penal provisions of Sections 316(2) and 318(4) of the Bharatiya Nyaya "
                  "Sanhita, 2023, causing wrongful loss to the Company and wrongful gain to yourself.")
        li.append("In case you fail to pay the aforesaid amount within 10 days from the date of receipt of "
                  "this notice, the Company will initiate appropriate legal proceedings, civil as well as "
                  "criminal, against you at your entire risk as to costs and consequences.")
        tail = []

    elif kind == "consumer":
        opening = None
        blocks.append(Block("p", text=(
            "We, CEAT Limited (“Company”), are in receipt of the Said Notice dated "
            f"{D(case,'notice_date')} issued on behalf of your client {V(case,'client_name')}, "
            f"{V(case,'client_relation','client’s stated relationship')}, residing at "
            f"{V(case,'client_address','client address')}. At the outset, the Said Notice is factually "
            "baseless, patently incorrect, mala fide and unsustainable under law. Unless specifically "
            "admitted, nothing in the Said Notice shall be deemed admitted or accepted by us.")))
        if case.get("blk_a") is not False:
            blocks.append(Block("p", text=(
                "A) We are engaged, inter alia, in manufacturing and marketing of tyres, tubes and flaps "
                "(“Products”). We sell our Products to our authorized dealers and to Original Equipment "
                "Manufacturers on a principal-to-principal basis. After such sale, we are not aware of "
                "onward sales by those dealers/OEMs to their customers/consumers.")))
        if case.get("blk_b") is not False:
            blocks.append(Block("p", text=(
                "B) The Products are subject to the warranty obligations detailed on our Company website, "
                "along with the procedure to claim warranty. Our procedure requires the tyre(s)/tube(s) "
                "under claim to be submitted for inspection; our Technical Service Engineer examines the "
                "item and the disposition is communicated with a copy of the inspection report.")))
        if case.get("blk_c") is not False:
            blocks.append(Block("p", text=(
                "C) It is an admitted fact that your client has not purchased tyres from us or our "
                f"authorized dealer. Your client purchased {V(case,'product','vehicle / product')} from "
                f"{V(case,'dealer','dealer / OEM')}. We have no contractual, commercial or legal "
                "relationship with your client. In the absence of privity of contract, we neither owe any "
                "obligation nor bear any responsibility towards your client.")))
        if str(case.get("claim_date", "")).strip() or str(case.get("inspection", "")).strip():
            t = (f"For the record: we received the warranty claim on {D(case,'claim_date','claim date')}; "
                 f"on inspection the item was found {V(case,'inspection','inspection finding')}, and it is "
                 "accordingly not eligible under our warranty policy")
            if str(case.get("rejection", "")).strip():
                t += f", which disposition was communicated to your client on {fmt_date(case['rejection'])}"
            blocks.append(Block("p", text=t + "."))
        blocks.append(Block("p", text="Now, we respond para-wise to your Said Notice as follows:"))
        for p in rows(case, "paras"):
            stance = str(p.get("stance", "Deny"))
            phrase = ("admit only to the limited extent stated below and deny the remainder"
                      if stance.startswith("Admit") else
                      ("are not aware of the averments and put your client to strict proof thereof"
                       if stance.startswith("Not aware") else "deny the contents thereof"))
            t = f"With reference to para {p.get('n')} of the Said Notice, we {phrase}."
            if str(p.get("text", "")).strip():
                t += " " + p["text"].strip()
            blocks.append(Block("p", text=t))
        if not rows(case, "paras"):
            blocks.append(Block("p", text=blank("para-wise responses — one per numbered paragraph")))
        dem = [x for x in rows(case, "demands") if str(x.get("d", "")).strip()]
        denied = [x["d"] for x in dem if not str(x.get("resp", "")).startswith("Conceded")]
        if denied:
            blocks.append(Block("p", text="The demands raised in the Said Notice, namely "
                                          + "; ".join(denied) + ", are wholly untenable and are hereby "
                                          "expressly denied and rejected."))
        for x in dem:
            if str(x.get("resp", "")).startswith("Conceded"):
                blocks.append(Block("p", text=f"In respect of your client's demand for {x['d']}, "
                                              f"{str(x.get('note','')).strip() or 'we shall act as stated separately'}."))
        blocks.append(Block("p", text="Under such circumstances, notwithstanding the above, if your client "
                                      "initiates proceedings against us, we shall have no alternative but to "
                                      "defend the same at your client's entire risk as to costs and consequences."))
        li, tail = [], []

    else:
        opening = None
        agr = V(case, "agreement_name", "agreement title")
        dt = D(case, "agreement_date")
        li.append("CEAT Limited (“the Company”) is a Public Limited Company incorporated under the Companies "
                  f"Act, 1956, having its Registered Office at {ro}, engaged in the manufacture and sale of "
                  "Tyres, Tubes and Flaps.")
        if kind == "breach":
            subject = f"Notice of Breach of {agr} dated {dt} — call to cure."
            li.append(f"The Company and you entered into {agr} dated {dt} (“the Agreement”).")
            li.append(f"In terms of Clause {V(case,'clause_no','clause')} of the Agreement, you were obliged "
                      f"to {V(case,'obligation','the obligation')}.")
            li.append(f"You are in breach of the said obligation, in that "
                      f"{V(case,'breach_facts','particulars of the breach')}. Despite the Company's "
                      "follow-ups, the breach subsists.")
            li.append(f"You are hereby called upon to remedy the aforesaid breach within "
                      f"{V(case,'cure_period','cure period')} from the date of receipt of this notice.")
            li.append("Should you fail to cure the breach within the said period, the Company shall be "
                      f"constrained to {V(case,'consequences','consequences')}, at your entire risk as to "
                      "costs and consequences.")
        elif kind == "termination":
            subject = f"Notice of Termination of {agr} dated {dt}."
            li.append(f"The Company and you entered into {agr} dated {dt} (“the Agreement”), governing "
                      f"{V(case,'subject_of','subject of the agreement')}.")
            g = str(case.get("ground", ""))
            if g == "Convenience":
                li.append(f"In terms of Clause {V(case,'clause_no','clause')}, the Company is entitled to "
                          f"terminate the Agreement by giving {V(case,'notice_period','notice period')} notice.")
            elif g == "Expiry":
                li.append(f"In terms of Clause {V(case,'clause_no','clause')}, the Agreement stands "
                          "terminated upon expiry of its term.")
            else:
                t = (f"In terms of Clause {V(case,'clause_no','clause')}, you were required to "
                     f"{V(case,'obligation','the obligation')}. You have failed to do so, as "
                     f"{V(case,'facts','facts of the breach')}.")
                if str(case.get("cure_given_date", "")).strip():
                    t += f" This is despite the cure period given on {fmt_date(case['cure_given_date'])}."
                li.append(t)
            li.append(f"Accordingly, the Company hereby gives notice of termination of the Agreement under "
                      f"Clause {V(case,'clause_no','clause')}, with effect from {D(case,'effective_date')}.")
            w = "Upon termination, you are called upon to "
            if str(case.get("dues", "")).strip():
                w += f"clear all outstanding dues of {M(case,'dues')}, and "
            li.append(w + V(case, "wind_down", "wind-down obligations") + ".")
        elif kind == "renewal":
            renew = case.get("intent") != "Do not renew"
            subject = f"Notice of {'Renewal' if renew else 'Non-Renewal'} of {agr} dated {dt}."
            li.append(f"CEAT Limited (“the Company”) and you are parties to {agr} dated {dt} (“the "
                      f"Agreement”), which is due to expire on {D(case,'expiry_date')}.")
            if renew:
                terms = str(case.get("revised_terms", "")).strip()
                li.append(f"In terms of Clause {V(case,'clause_no','clause')}, the Company hereby conveys "
                          f"its intention to renew the Agreement for a further term of "
                          f"{V(case,'renewal_term','renewal term')}"
                          + (f" on the following revised terms: {terms}" if terms else " on the existing terms")
                          + f". Kindly confirm your acceptance on or before {D(case,'confirm_by','confirm-by date')}.")
            else:
                li.append(f"In terms of Clause {V(case,'clause_no','clause')}, the Company hereby gives "
                          "notice that it does NOT intend to renew the Agreement, which shall accordingly "
                          f"stand expired on {D(case,'expiry_date')} without further notice.")
                w = "Upon expiry, you are called upon to "
                if str(case.get("dues", "")).strip():
                    w += f"clear outstanding dues of {M(case,'dues')}, and "
                li.append(w + V(case, "wind_down", "wind-down obligations") + ".")
        elif kind == "fm":
            subject = f"Notice invoking Force Majeure under {agr} dated {dt}."
            li.append(f"The Company and you are parties to {agr} dated {dt} (“the Agreement”), which "
                      f"contains a force majeure provision at Clause {V(case,'clause_no','clause')}.")
            li.append(f"On/from {D(case,'fm_date','event date')}, {V(case,'fm_event','the event')} has "
                      "occurred, being an event beyond the Company's reasonable control within the meaning "
                      f"of Clause {V(case,'clause_no','clause')}.")
            li.append("As a direct consequence, the Company is prevented/delayed from performing "
                      f"{V(case,'affected','affected obligations')}. The expected impact/duration is "
                      f"{V(case,'impact','impact / duration')}.")
            li.append("The Company is taking the following steps to mitigate the effect of the said event: "
                      f"{V(case,'mitigation','mitigation steps')}.")
            li.append(f"Accordingly, in terms of Clause {V(case,'clause_no','clause')}, the Company hereby "
                      "invokes force majeure and calls upon you to treat the affected obligations as "
                      f"suspended for the duration of the event, and to {V(case,'relief','relief sought')}.")
        elif kind == "price":
            subject = f"Notice of Price Revision effective {D(case,'effective_date')}."
            basis = (f"Clause {case['clause_no']}" if str(case.get("clause_no", "")).strip()
                     else "the Company's right to revise prices")
            li.append(f"CEAT Limited (“the Company”) supplies its Tyres, Tubes and Flaps (“Goods”) to you "
                      f"under {agr}" + (f" dated {fmt_date(case['agreement_date'])}"
                                        if str(case.get("agreement_date", "")).strip() else "") + ".")
            li.append(f"On account of {V(case,'reason','reason for the revision')}, and in terms of {basis}, "
                      "the Company hereby gives notice of a revision in the prices of the Goods with effect "
                      f"from {D(case,'effective_date')}.")
            prows = [r for r in rows(case, "prices") if str(r.get("sku", "")).strip()]
            if prows:
                li.append(("The revised prices are as follows:",
                           dict(head=["Product / SKU", "Existing Price", "Revised Price", "% change"],
                                rows=[[r.get("sku"), fmt_amount(r.get("old")) or "—",
                                       fmt_amount(r.get("nw")) or "—", r.get("pct", "—")] for r in prows])))
            else:
                li.append("The revised prices are as follows: " + blank("price table"))
            li.append(f"Orders placed and accepted before {D(case,'effective_date')} shall be "
                      f"{V(case,'pre_orders','treatment of pre-existing orders')}. All orders on or after "
                      f"{D(case,'effective_date')} shall be at the revised prices.")
            li.append("All other terms and conditions of supply remain unchanged.")
        li.append("This notice is issued without prejudice to the Company's rights and remedies, all of "
                  "which are expressly reserved.")
        tail = []

    blocks.append(Block("subject", text="Sub: " + subject, bold=True))
    blocks.append(Block("p", text="Dear Sir/Madam," if kind == "consumer" else "Sir/Madam,"))
    if opening:
        blocks.append(Block("p", text=opening))
    if li:
        blocks.append(Block("ol", items=li))
    for t in tail:
        blocks.append(Block("p", text=t))
    if str(case.get("jurisdiction", "")).strip() and kind in ("s138", "recovery"):
        blocks.append(Block("p", text="Without prejudice to the Company's other rights, any legal "
                                      "proceedings arising out of or in connection with this notice shall be "
                                      f"subject to the jurisdiction of the courts at {case['jurisdiction']}."))
    blocks.append(Block("sig", text=sig_block(case)))
    return subject, blocks


# --------------------------------------------------------------------------
def to_text(kind: str, case: dict) -> str:
    lh = SK.letterhead()
    subject, blocks = build(kind, case)
    out = [lh["name"], lh["address"], lh["meta"], ""]
    for b in blocks:
        if b.kind == "ol":
            for i, it in enumerate(b.items, 1):
                if isinstance(it, tuple):
                    out.append(f"{i}. {it[0]}")
                    t = it[1]
                    out.append("   " + " | ".join(t["head"]))
                    for r in t["rows"]:
                        out.append("   " + " | ".join(str(c) for c in r))
                else:
                    out.append(f"{i}. {it}")
                out.append("")
        else:
            out.append(b.text)
            out.append("")
    return "\n".join(out).strip() + "\n"


def to_docx(kind: str, case: dict) -> bytes:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor, Cm
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    lh = SK.letterhead()
    subject, blocks = build(kind, case)
    doc = docx.Document()

    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(2)
        s.left_margin = s.right_margin = Cm(2)

    style = doc.styles["Normal"]
    style.font.name = "Georgia"
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Georgia")

    def para(text, *, size=11, bold=False, underline=False, align=None,
             space_after=8, pre=False):
        p = doc.add_paragraph()
        if align:
            p.alignment = align
        pf = p.paragraph_format
        pf.space_after = Pt(space_after)
        pf.line_spacing = 1.35
        for i, line in enumerate(str(text).split("\n")):
            r = p.add_run(("" if i == 0 else "") + line)
            r.bold = bold
            r.underline = underline
            r.font.size = Pt(size)
            if i < len(str(text).split("\n")) - 1:
                r.add_break()
        return p

    def bottom_border(p, color="9C7A3C", sz=12):
        pPr = p._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        bot = OxmlElement("w:bottom")
        bot.set(qn("w:val"), "single"); bot.set(qn("w:sz"), str(sz))
        bot.set(qn("w:space"), "4"); bot.set(qn("w:color"), color)
        bdr.append(bot); pPr.append(bdr)

    # letterhead
    para(lh["name"], size=15, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    para(lh["address"], size=9, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=1)
    p = para(lh["meta"], size=8, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14)
    bottom_border(p)

    for b in blocks:
        if b.kind == "ol":
            for i, it in enumerate(b.items, 1):
                text, tbl = (it if isinstance(it, tuple) else (it, None))
                p = doc.add_paragraph(style="List Number")
                p.paragraph_format.space_after = Pt(7)
                p.paragraph_format.line_spacing = 1.35
                p.add_run(str(text))
                if tbl:
                    t = doc.add_table(rows=1, cols=len(tbl["head"]))
                    t.style = "Table Grid"
                    for c, h in zip(t.rows[0].cells, tbl["head"]):
                        run = c.paragraphs[0].add_run(str(h))
                        run.bold = True
                        run.font.size = Pt(9)
                    for row in tbl["rows"]:
                        cells = t.add_row().cells
                        for c, v in zip(cells, row):
                            r = c.paragraphs[0].add_run(str(v))
                            r.font.size = Pt(9)
                    doc.add_paragraph().paragraph_format.space_after = Pt(4)
        elif b.kind in ("stamp", "subject"):
            para(b.text, bold=True, underline=b.underline, size=10.5, space_after=4)
        elif b.kind in ("addr", "sig"):
            para(b.text, space_after=14)
        else:
            para(b.text)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def filename(kind: str, case: dict, specimen: bool = False) -> str:
    import re
    key = {"s138": "Section138_Notice", "recovery": "Recovery_Notice",
           "consumer": "Consumer_Notice_Reply", "breach": "Breach_Notice",
           "termination": "Termination_Notice", "renewal": "Renewal_Notice",
           "fm": "Force_Majeure_Notice", "price": "Price_Revision_Notice"}.get(kind, "Notice")
    party = case.get("client_name") if kind == "consumer" else case.get("noticee_name")
    party = re.sub(r"[^A-Za-z0-9]+", "_", str(party or "Party")).strip("_")[:40] or "Party"
    d = case.get("reply_date") if kind == "consumer" else case.get("notice_date")
    from .words import parse_date
    dt = parse_date(d) or __import__("datetime").date.today()
    return f"CEAT_{key}_{party}_{dt:%Y%m%d}{'_FILL-IN' if specimen else ''}.docx"
