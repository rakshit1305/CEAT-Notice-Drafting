"""The four contract notices: termination, force majeure, renewal, price.

Same idea as ``fixtures.py``, but these four matters are not "defective vs
fixed" pairs. Each is one complete, internally consistent matter that a drafter
would hand over, and each is expected to validate clean
(``validate(kind, case).ok and not r.blanks``) and to draft without a
read-through complaint.

What each one is there to exercise:

    TERM    the obligation clause (7.2) and the termination clause (12.1(a))
            are different clauses and must stay apart; the obligation is typed
            as a verb phrase beginning "to …"; the wind-down answer is a list
            of five items and already covers the outstanding dues, so the dues
            must not be demanded twice in the same sentence; the facts rely on
            19 claims with no schedule annexed.
    FM      answers typed as fragments that cannot simply be appended ("CEAT's
            scheduled despatches…", "production … will remain suspended…");
            five mitigation steps that belong in a lettered list, one of them
            written as "CEAT will …" where the notice must say "the Company";
            a quantities table that totals 800 / 160 / 640; the notice is
            dated 8 days after the event began.
    REN     a partnership firm stays Noticee No. 1 with its partners under it;
            five revised terms, two carrying bare rupee figures (200000 and
            18000000) that must be written in house style; acceptance is asked
            for before expiry; 100 days remain to expiry, which is what makes
            a 120-day non-renewal notice time-barred.
    PRICE   a SKU-wise table typed by hand (sku | old | nw | pct), effective
            more than 30 days after the notice date.
"""

_SIGNATORY = dict(signatory_name="Ms. Meena Marar",
                  signatory_desig="General Manager – Legal")


# ============================================================ Termination ===
# A Nagpur dealership terminated for warranty-claim fraud. The cure period was
# given on 10.08.2026 and lapsed on 25.08.2026; the notice is dated 14.09.2026
# and takes effect on 30.09.2026.
TERM = {
    "_defaults": [],
    "noticee_type": "Company + directors",
    "noticee_name": "M/s Konark Auto Agencies Private Limited",
    "noticee_address": "Plot 7, Wardha Road, Nagpur – 440015",
    "directors": [
        {"name": "Mr. Prashant Deshmukh", "address": "Flat 12B, Laxmi Nagar, Nagpur – 440022"},
        {"name": "Mrs. Vaishali Deshmukh", "address": "Flat 12B, Laxmi Nagar, Nagpur – 440022"},
    ],
    "agreement_name": "Dealership Agreement",
    "agreement_date": "2023-07-01",
    "subject_of": "the appointment of your company as an authorised CEAT dealer for the Nagpur "
                  "territory under dealer code CEAT/S/NGP/0511 and the supply of Goods "
                  "thereunder",
    # the right to terminate
    "clause_no": "12.1(a)",
    "ground": "Breach",
    # the obligation breached sits in a different clause, and is typed as a
    # verb phrase beginning "to …"
    "obligation_clause": "7.2",
    "obligation": "to register every warranty claim on the Company's dealer portal within 48 "
                  "hours of receipt of the tyre and to retain the claimed tyre for inspection",
    "facts": "a review of the warranty claims lodged from your dealership between January and "
             "June 2026 found that 19 claims were raised on tyres whose serial numbers had been "
             "buffed and re-embossed, and that the credits taken against those claims were not "
             "due to you",
    "cure_given_date": "2026-08-10",
    "cure_lapsed_date": "2026-08-25",
    "notice_period": "",
    "effective_date": "2026-09-30",
    # the item-by-item particulars were not annexed — which is what the
    # "schedule of particulars" prompt is for
    "schedule": [],
    "deposit_held": "100000",
    "effect_on_receipt": "Yes",
    "dues": "124400",
    "wind_down":
        "pay the balance outstanding of INR 1,24,400/- within 15 (FIFTEEN) days of receipt of "
        "this notice\n"
        "return all Company property, display material and signage\n"
        "cease all use of the CEAT trade marks, trade name and dealer board\n"
        "hand over the dealer board, the dealership certificate and the unused claim forms\n"
        "retain every tyre held under the 19 pending claims for inspection by the Company's "
        "Technical Service Engineer",
    "prior": "No",
    "mode": "BY SPEED POST",
    "notice_date": "2026-09-14",
    "authority_confirmed": True,
    "extra_notes": "",
    **_SIGNATORY,
}


# ========================================================== Force majeure ===
# CEAT invoking force majeure against a fleet customer after flooding at the
# Nashik plant. The event began on 10.08.2026; the notice is dated 18.08.2026.
FM = {
    "_defaults": [],
    "noticee_type": "Company + directors",
    "noticee_name": "M/s Sahyadri Roadlines Private Limited",
    "noticee_address": "Plot 22, MIDC Satpur, Nashik – 422007",
    # the notice is addressed to the company. Mr. Sawant is the contact person
    # it is marked for the attention of — not a noticee.
    "directors": [],
    "attn_name": "Mr. Rahul Sawant",
    "attn_desig": "Director – Operations",
    "agreement_name": "Supply Agreement",
    "agreement_date": "2024-09-11",
    "clause_no": "14",
    "direction": "CEAT is invoking force majeure",
    "fm_event": "flooding at the Company's Nashik plant following the evacuation order issued "
                "by the District Collector, Nashik",
    "fm_date": "2026-08-10",
    # typed in the third person, as the drafter wrote it
    "affected": "CEAT's scheduled despatches of truck and bus radial tyres under your purchase "
                "orders for September and October 2026",
    # a clause, not a noun phrase: it needs "is that …" in front of it
    "impact": "production at the Nashik plant will remain suspended for approximately 6 to 8 "
              "weeks and despatches will be delayed accordingly",
    "mitigation":
        "120 units have been re-allocated from the Halol plant and will be despatched by "
        "05.09.2026\n"
        "the balance volumes are being re-planned at the Ambernath plant\n"
        "alternative transporters have been engaged for despatches out of Halol\n"
        "your purchase orders have been re-sequenced to protect the earliest delivery dates\n"
        "CEAT will send a weekly status report until the event ceases",
    "quantities": [
        {"period": "September 2026", "sched": "400", "done": "160", "pend": "240",
         "due": "2026-09-25"},
        {"period": "October 2026", "sched": "400", "done": "0", "pend": "400",
         "due": "2026-10-25"},
    ],
    "fm_continue": "if the event continues beyond 60 days, either party may terminate the "
                   "Agreement on 15 days' written notice under Clause 14.4",
    "relief": "extend the delivery timelines by a period equivalent to the duration of the "
              "force majeure event",
    "mode": "THROUGH SPEED POST / EMAIL / WHATSAPP",
    "email": "rahul.sawant@sahyadriroadlines.example",
    "notice_date": "2026-08-18",
    "authority_confirmed": True,
    "extra_notes": "",
    **_SIGNATORY,
}


# =============================================================== Renewal ===
# A Satara partnership whose dealership expires on 31.12.2026. The notice is
# dated 22.09.2026 — exactly 100 days before expiry.
REN = {
    "_defaults": [],
    "noticee_type": "Partnership + partners",
    "noticee_name": "M/s Om Sai Tyres & Services",
    "noticee_address": "Survey No. 112, Pune–Satara Road, Satara – 415002",
    "directors": [
        {"name": "Mr. Harish Patel", "address": ""},
        {"name": "Mr. Nilesh Patel", "address": ""},
    ],
    "agreement_name": "Dealership Agreement",
    "agreement_date": "2024-01-01",
    "expiry_date": "2026-12-31",
    "clause_no": "3.2",
    "intent": "Renew",
    "renewal_term": "2 (TWO) years",
    # typed with bare figures, one item per line
    "revised_terms":
        "a further term of 2 (TWO) years with effect from 01.01.2027\n"
        "an annual purchase target of 18000000 for the renewed term\n"
        "security deposit of 200000 to be maintained with the Company throughout the renewed "
        "term\n"
        "payment for all Goods within 30 days of the date of each invoice\n"
        "territory restricted to the Satara and Sangli districts",
    "confirm_by": "2026-11-30",
    "notice_period": "",
    "wind_down": "",
    "mode": "BY SPEED POST",
    "notice_date": "2026-09-22",
    "authority_confirmed": True,
    "extra_notes": "",
    **_SIGNATORY,
}


# ========================================================= Price revision ===
# A SKU-wise revision of 6.2%, notified on 20.08.2026 and effective 25.09.2026.
PRICE = {
    "_defaults": [],
    "noticee_type": "Individual / sole proprietor",
    "noticee_name": "Mr. Suresh Nair",
    "firm_name": "M/s Nair Tyre Centre",
    "noticee_address": "Shop 3, Market Road, Ernakulam – 682035",
    "agreement_name": "Dealership Agreement",
    "agreement_date": "2025-03-04",
    "clause_no": "9.3",
    "reason": "a sustained increase in the cost of natural rubber and carbon black",
    "prices": [
        {"sku": "TBR-2958 295/80 R22.5", "old": "24500", "nw": "26020", "pct": "+6.2%"},
        {"sku": "LCV-0750 7.50-16", "old": "6450", "nw": "6850", "pct": "+6.2%"},
    ],
    # the table is given, so no overall percentage is stated
    "price_change_pct": "",
    "effective_date": "2026-09-25",
    "pre_orders": "honoured at the existing prices provided despatch is taken within 30 "
                  "(THIRTY) days of the effective date",
    "mode": "BY SPEED POST",
    "notice_date": "2026-08-20",
    "authority_confirmed": True,
    "extra_notes": "",
    **_SIGNATORY,
}
