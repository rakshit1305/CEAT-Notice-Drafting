"""The four reviewed matters, each twice: as it went wrong, and as corrected.

Every dict here is a *case* — the answers one drafter typed into the console for
one notice. The keys are the field keys of ``core.schema`` (see QUESTIONS and
TABLE_COLS); the values are what a person would actually have typed, warts and
all.

The four plain names (S138, RECOVERY, CONSUMER, BREACH) are the DEFECTIVE
matters. Each one reproduces a specific defect found when the agent's notices
were reviewed, so that ``core.validate`` can be shown to stop or flag it:

    S138      the demand is the INVOICE total (4,48,000) on a 2,00,000 cheque,
              with a "no further part-payment" note used as the explanation;
              the raw briefing note is sitting in the background answer and the
              nature of business is a relationship, not a line of business.
    RECOVERY  the statement of account carries two invoices (3,79,500) that had
              not fallen due on the notice date; the prior-notice question was
              never answered; interest is demanded with no start date.
    CONSUMER  CEAT's own name and Worli address are in the consumer's slot; a
              warranty claim date is recorded with no inspection finding; the
              para-wise reply calls the dealer "authorised" while block C
              denies privity; the reply carries the same date as the incoming
              notice; para 2 denies and then admits part of the same point.
    BREACH    the noticee is a sole proprietorship named only by its firm name;
              three answers are pasted into the middle of template sentences;
              Clause 18.1 is cited as breached and never explained.

The four _FIXED names are the SAME matters with those defects corrected, and
nothing else changed. ``validate(kind, case).ok and not case_report.blanks``
is expected of them.

Figures are internally consistent on purpose: the invoice total, the cheque
total, the part-payment and the sum demanded actually reconcile, and the dates
run in order. Anything that does not reconcile in a defective fixture does not
reconcile because that is the defect.
"""

# --------------------------------------------------------------------------
# the party common to the cheque and recovery matters
# --------------------------------------------------------------------------
_HIGHWAY = "M/s Highway Auto Spares Private Limited"
_HIGHWAY_ADDR = "14, Industrial Area Phase II, Chandigarh – 160002"
_HIGHWAY_DIRS = [
    {"name": "Mr. Gurpreet Singh Bedi",
     "address": "House No. 2041, Sector 21-C, Chandigarh – 160022"},
    {"name": "Mrs. Harleen Kaur Bedi",
     "address": "House No. 2041, Sector 21-C, Chandigarh – 160022"},
]

_SIGNATORY = dict(signatory_name="Ms. Meena Marar",
                  signatory_desig="General Manager – Legal")


# ========================================================== Section 138 ===
# One invoice of INR 4,48,000. One cheque of INR 2,00,000 towards part of it.
# The cheque was returned unpaid. Nothing has been paid since.
_S138_INVOICES = [
    {"no": "CEAT/CH/2026/0298", "date": "2026-05-28", "amt": "448000"},
]
_S138_CHEQUES = [
    {"no": "004512", "date": "2026-06-12", "amt": "200000",
     "bank": "HDFC Bank Ltd., Sector 17-B, Chandigarh",
     "dis": "2026-06-20", "reason": "Funds Insufficient", "memo": "2026-06-20"},
]

S138 = {
    "_defaults": [],
    "noticee_type": "Company + directors",
    "noticee_name": _HIGHWAY,
    "noticee_address": _HIGHWAY_ADDR,
    "directors": [dict(d) for d in _HIGHWAY_DIRS],
    # typed as a relationship, not as a line of business — it reaches the
    # notice as "engaged in Dealership of CEAT tyres…"
    "business": "Dealership of CEAT tyres, tubes and flaps in the Chandigarh territory",
    # the whole internal briefing note, pasted into the answer box
    "background":
        "1. Highway Auto Spares Private Limited was appointed as an authorised CEAT dealer for "
        "the Chandigarh territory on 01.04.2022 on 30 days' credit.\n"
        "2. Cheque No. 004512 dated 12.06.2026 for Rs. 2,00,000 was issued towards part of the "
        "outstanding.\n"
        "3. Invoice No. CEAT/CH/2026/0298 dated 28.05.2026 for Rs. 4,48,000 remains unpaid.\n"
        "4. The cheque was returned unpaid on 20.06.2026 for want of funds.",
    "invoices": [dict(r) for r in _S138_INVOICES],
    "cheques": [dict(r) for r in _S138_CHEQUES],
    "presented_date": "2026-06-18",
    "dishonour_date": "2026-06-20",
    "dishonour_reason": "Funds Insufficient",
    "memo_date": "2026-06-20",
    # THE DEFECT: the invoice total, not the cheque amount
    "amount": "448000",
    # and the sentence that was treated as an explanation for the difference
    "part_payment": "No further part-payment has been made. Amount demanded is limited to "
                    "INR 2,00,000/-.",
    "jurisdiction": "Chandigarh",
    "prior": "",
    "mode": "BY SPEED POST",
    "notice_date": "2026-07-10",
    "extra_notes": "",
    **_SIGNATORY,
}

S138_FIXED = {
    "_defaults": [],
    "noticee_type": "Company + directors",
    "noticee_name": _HIGHWAY,
    "noticee_address": _HIGHWAY_ADDR,
    "directors": [dict(d) for d in _HIGHWAY_DIRS],
    "business": "the business of purchase and sale of tyres, tubes and flaps",
    "background":
        "Noticee No. 1 was appointed as an authorised CEAT dealer for the Chandigarh territory "
        "on 01.04.2022 and has since purchased Goods from the Company on 30 days' credit.",
    "invoices": [dict(r) for r in _S138_INVOICES],
    "cheques": [dict(r) for r in _S138_CHEQUES],
    "presented_date": "2026-06-18",
    "dishonour_date": "2026-06-20",
    "dishonour_reason": "Funds Insufficient",
    "memo_date": "2026-06-20",
    # the cheque amount, nothing having been received since dishonour
    "amount": "200000",
    "part_paid": "0",
    "jurisdiction": "Chandigarh",
    "prior": "No",
    "mode": "BY SPEED POST",
    "notice_date": "2026-07-10",
    "authority_confirmed": True,
    "extra_notes": "",
    **_SIGNATORY,
}


# ============================================================= Recovery ===
# The running account of the same dealership. Five invoices; the notice is
# dated 31.07.2026, so the last two had not fallen due on the notice's own
# 30-day terms.
_RECOVERY_SOA = [
    {"ref": "CEAT/CH/2026/0251", "date": "2026-04-12", "amt": "162500"},
    {"ref": "CEAT/CH/2026/0267", "date": "2026-05-04", "amt": "248650"},
    {"ref": "CEAT/CH/2026/0298", "date": "2026-05-28", "amt": "448000"},
    {"ref": "CEAT/CH/2026/0331", "date": "2026-07-06", "amt": "215000"},   # due 05.08.2026
    {"ref": "CEAT/CH/2026/0344", "date": "2026-07-18", "amt": "164500"},   # due 17.08.2026
]
_RECOVERY_TOTAL = "1238650"        # 1,62,500 + 2,48,650 + 4,48,000 + 2,15,000 + 1,64,500

RECOVERY = {
    "_defaults": [],
    "noticee_type": "Company + directors",
    "noticee_name": _HIGHWAY,
    "noticee_address": _HIGHWAY_ADDR,
    "directors": [dict(d) for d in _HIGHWAY_DIRS],
    "relationship": "Appointed as an authorised CEAT dealer for the Chandigarh territory on "
                    "01.04.2022, purchasing Goods on 30 days' credit.",
    "soa": [dict(r) for r in _RECOVERY_SOA],
    "amount": _RECOVERY_TOTAL,
    "as_on_date": "2026-07-31",
    "interest": "8",
    # THE DEFECT: interest demanded with no start date
    "interest_from": "",
    "jurisdiction": "Mumbai",
    # THE DEFECT: never answered, and must not be read as "no"
    "prior": "",
    "prior_date": "",
    "prior_ref": "",
    "mode": "BY SPEED POST",
    # THE DEFECT: dated before CEAT/CH/2026/0331 and /0344 fell due
    "notice_date": "2026-07-31",
    "extra_notes": "",
    **_SIGNATORY,
}

RECOVERY_FIXED = {
    "_defaults": [],
    "noticee_type": "Company + directors",
    "noticee_name": _HIGHWAY,
    "noticee_address": _HIGHWAY_ADDR,
    "directors": [dict(d) for d in _HIGHWAY_DIRS],
    "relationship": "Appointed as an authorised CEAT dealer for the Chandigarh territory on "
                    "01.04.2022, purchasing Goods on 30 days' credit.",
    "soa": [dict(r) for r in _RECOVERY_SOA],
    "amount": _RECOVERY_TOTAL,
    "as_on_date": "2026-08-18",
    "interest": "8",
    "interest_from": "from the due date of each invoice",
    "jurisdiction": "Mumbai",
    # the Section 138 notice on the dishonoured cheque went out on 20.06.2026.
    # It covered invoice CEAT/CH/2026/0298, which is also in the statement of
    # account below — the overlap the validator is expected to flag.
    "prior": "Yes",
    "prior_date": "2026-06-20",
    "prior_ref": "Notice dated 20.06.2026 under Section 138 of the Negotiable Instruments Act, "
                 "1881 in respect of dishonoured cheque no. 004512, which was issued against "
                 "invoice CEAT/CH/2026/0298",
    "current_instrument": "This notice is confined to the outstanding invoices set out in the "
                          "statement of account and does not repeat the demand made under the "
                          "said notice dated 20.06.2026.",
    "mode": "BY SPEED POST",
    # every invoice in the statement has fallen due on this date
    "notice_date": "2026-08-20",
    "authority_confirmed": True,
    "extra_notes": "",
    **_SIGNATORY,
}


# ============================================================= Consumer ===
# The incoming notice, as pasted into the answer box. Six numbered paragraphs,
# so six para-wise responses are required.
_INCOMING = """ADVOCATE S. KRISHNAN, B.A., LL.B.
22 Law Chambers, Chennai - 600104

LEGAL NOTICE

To,
CEAT Limited, RPG House, 463 Dr. Annie Besant Road, Worli, Mumbai - 400030

Under instructions from and on behalf of my client Mr. A. Kumar, owner of vehicle
TN-09-AB-1234, residing at New No. 18, Thiruvalluvar Street, Ashok Nagar, Chennai - 600083,
I serve upon you the following notice:

1. That my client is the owner of the said vehicle and is a consumer within the meaning of the
Consumer Protection Act, 2019.
2. That my client purchased four CEAT tyres of size 215/75 R15 on 14.03.2026 from Gill Tyre
House, Anna Salai, Chennai, for a total consideration of Rs. 32,000/-.
3. That within eight weeks of purchase my client noticed abnormal and uneven wear on all four
tyres, and bulges on two of them.
4. That my client lodged a warranty claim with the said dealer on 12.05.2026 and handed over
the tyres for inspection.
5. That no inspection report has been furnished to my client till date, the claim has neither
been allowed nor rejected in writing, and my client has been constrained to incur a sum of
Rs. 30,000/- on replacement tyres.
6. That you are therefore called upon to comply with the demands set out below within fifteen
days of receipt hereof, failing which my client shall be constrained to approach the District
Consumer Disputes Redressal Commission for appropriate relief.

My client's demands are:
(a) Replace four tyres free of cost or refund INR 32,000/-;
(b) Pay INR 50,000/- towards compensation for mental agony and harassment;
(c) Pay INR 25,000/- towards replacement tyres purchased;
(d) Pay INR 20,000/- towards cost of legal notice.

Adv. S. Krishnan
Dated: 04.08.2026
"""

# The four demands, exactly as the incoming notice words them.
_DEMANDS = [
    {"d": "Replace four tyres free of cost or refund INR 32,000/-",
     "resp": "Denied",
     "note": "the tyres were examined and the condition found was impact damage and sustained "
             "under-inflation, which the limited warranty does not cover"},
    {"d": "Pay INR 50,000/- towards compensation for mental agony and harassment",
     "resp": "Denied",
     "note": "no cause of action in damages arises against the Company"},
    {"d": "Pay INR 25,000/- towards replacement tyres purchased",
     "resp": "Denied",
     "note": "no bill or receipt for the replacement tyres has been produced"},
    {"d": "Pay INR 20,000/- towards cost of legal notice",
     "resp": "Denied",
     "note": "the Said Notice is misconceived and the costs of it are not payable by the Company"},
]

CONSUMER = {
    "_defaults": [],
    "incoming": _INCOMING,
    "advocate_name": "Adv. S. Krishnan",
    "advocate_address": "22 Law Chambers, Chennai – 600104",
    "notice_ref": "",
    # THE DEFECT: CEAT's own name, address and role are in the consumer's slot
    "client_name": "CEAT Limited",
    "client_relation": "manufacturer of the tyres complained of",
    "client_address": "RPG House, 463 Dr. Annie Besant Road, Worli, Mumbai – 400030",
    "product": "four CEAT tyres of size 215/75 R15",
    "dealer": "Gill Tyre House, Anna Salai, Chennai",
    # THE DEFECT: never answered, so block C cannot be decided
    "dealer_authorised": "",
    "claim_date": "2026-05-12",
    # THE DEFECT: a claim date with no inspection finding behind it
    "inspection": "",
    "rejection": "",
    "paras": [
        {"n": "1", "stance": "Deny", "text": ""},
        # THE DEFECT: denies, then admits part of the same point, and calls the
        # dealer "authorised" while block C denies privity
        {"n": "2", "stance": "Deny",
         "text": "The tyres were purchased from Gill Tyre House, our authorised dealer, and that "
                 "purchase is not disputed; the remaining averments are denied."},
        {"n": "3", "stance": "Deny", "text": ""},
        {"n": "4", "stance": "Not aware", "text": ""},
        {"n": "5", "stance": "Deny", "text": ""},
        {"n": "6", "stance": "Deny", "text": ""},
    ],
    "demands": [dict(r) for r in _DEMANDS],
    "goodwill": "",
    "warranty_note": "",
    # THE DEFECT: the reply carries the date printed on the incoming notice
    "notice_date": "2026-08-04",
    "reply_date": "2026-08-04",
    "mode": "BY SPEED POST",
    **_SIGNATORY,
}

CONSUMER_FIXED = {
    "_defaults": [],
    "incoming": _INCOMING,
    "advocate_name": "Adv. S. Krishnan",
    "advocate_address": "22 Law Chambers, Chennai – 600104",
    "notice_ref": "",
    "client_name": "Mr. A. Kumar",
    "client_relation": "owner of vehicle TN-09-AB-1234",
    "client_address": "New No. 18, Thiruvalluvar Street, Ashok Nagar, Chennai – 600083",
    "product": "four CEAT tyres of size 215/75 R15",
    "dealer": "Gill Tyre House, Anna Salai, Chennai",
    "dealer_authorised": "Yes",
    "claim_date": "2026-05-12",
    "inspection": "to have sustained impact damage and to have been run in a severely "
                  "under-inflated condition, and not to carry any manufacturing defect",
    "rejection": "2026-05-26",
    "paras": [
        {"n": "1", "stance": "Not aware", "text": ""},
        {"n": "2", "stance": "Admit in part",
         "text": "The Company's records show that the tyres were sold by the Company to Gill "
                 "Tyre House, an authorised CEAT dealer, and that the onward sale to your "
                 "client was a sale by that dealer on a principal-to-principal basis."},
        {"n": "3", "stance": "Deny",
         "text": "The tyres were examined by the Company's Technical Service Engineer and the "
                 "wear complained of was found to be the result of impact damage and sustained "
                 "under-inflation, and not of any manufacturing defect."},
        {"n": "4", "stance": "Deny", "text": ""},
        {"n": "5", "stance": "Deny",
         "text": "Your client has produced no bill or receipt for 30000 said to have been spent "
                 "on replacement tyres, and strict proof thereof is demanded."},
        {"n": "6", "stance": "Deny",
         "text": "The demands for replacement, refund and compensation set out in the Said "
                 "Notice are each untenable for the reasons stated above."},
    ],
    "demands": [dict(r) for r in _DEMANDS],
    "goodwill": "willing to inspect the four tyres within 15 days of receipt of this reply, "
                "against a claim receipt, without admission of liability",
    "warranty_note": "",
    "notice_date": "2026-08-04",
    "reply_date": "2026-08-14",
    "mode": "BY SPEED POST",
    "authority_confirmed": True,
    **_SIGNATORY,
}


# =============================================================== Breach ===
# A Pune proprietorship. Three invoices unpaid; the figures add up to the total
# the notice states.
_BREACH_INVOICE_LINES = (
    "Invoice CEAT/PN/2026/0451 dated 18.05.2026, outstanding INR 2,84,000\n"
    "Invoice CEAT/PN/2026/0478 dated 02.06.2026, outstanding INR 3,12,500\n"
    "Invoice CEAT/PN/2026/0502 dated 19.06.2026, outstanding INR 1,94,000\n"
    "The total outstanding on your account is INR 7,90,500/- as on 31.07.2026"
)

BREACH = {
    "_defaults": [],
    "noticee_type": "Individual / sole proprietor",
    # THE DEFECT: a proprietorship named only by its firm name — no person
    "noticee_name": "M/s Deccan Auto Tyres",
    "firm_name": "M/s Deccan Auto Tyres",
    "noticee_address": "Plot 12, Shivaji Nagar, Pune – 411005",
    "agreement_name": "Dealership Agreement",
    "agreement_date": "2025-03-04",
    # THE DEFECT: 18.1 is cited as breached and never explained anywhere
    "clause_no": "9.1, 9.2 and 18.1",
    # THE DEFECT: a noun phrase pasted after "you were obliged to"
    "obligation": "Timely payment of all invoices within 30 (THIRTY) days of the invoice date "
                  "and interest at 8% per annum on overdue amounts, as required by Clause 9.1",
    # THE DEFECT: a full sentence pasted after "in that", ending in a full stop
    "breach_facts": "Under Clause 9.2 you have failed to pay the following invoices despite "
                    "repeated reminders:\n" + _BREACH_INVOICE_LINES + ".",
    "cure_period": "15 (FIFTEEN) days",
    # THE DEFECT: a conditional sentence pasted after "constrained to", ending
    # in a full stop, so the template's ", at your entire risk" follows a stop
    "consequences": "If the breach is not cured, CEAT will terminate the Dealership Agreement "
                    "and initiate proceedings for recovery of the dues and losses.",
    "prior": "",
    "mode": "BY SPEED POST",
    "notice_date": "2026-08-05",
    "extra_notes": "",
    **_SIGNATORY,
}

BREACH_FIXED = {
    "_defaults": [],
    "noticee_type": "Individual / sole proprietor",
    "noticee_name": "Mr. Sanjay Kulkarni",
    "firm_name": "M/s Deccan Auto Tyres",
    "noticee_address": "Plot 12, Shivaji Nagar, Pune – 411005",
    "agreement_name": "Dealership Agreement",
    "agreement_date": "2025-03-04",
    "clause_no": "9.1 and 9.2",
    "obligation": "pay for all Products within 30 (THIRTY) days of each invoice and pay "
                  "interest at 8% per annum on overdue amounts",
    "breach_facts": "you have not paid the following invoices, in breach of Clause 9.2:\n"
                    + _BREACH_INVOICE_LINES,
    "cure_period": "15 (FIFTEEN) days",
    "consequences": "terminate the Dealership Agreement and initiate proceedings for recovery "
                    "of the dues and losses",
    "prior": "No",
    "mode": "BY SPEED POST",
    "notice_date": "2026-08-05",
    "authority_confirmed": True,
    "extra_notes": "",
    **_SIGNATORY,
}
