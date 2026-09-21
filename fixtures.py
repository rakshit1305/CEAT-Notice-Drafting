"""The four matters the agent drafted badly, reconstructed from its outputs.

These are the regression cases: every defect found in the review of those
notices is asserted against them in test_regressions.py.
"""
HIGHWAY = dict(
    noticee_type="Company + directors",
    noticee_name="M/s Highway Auto Spares Private Limited",
    noticee_address="14, Industrial Area Phase II, Chandigarh – 160002",
    directors=[
        {"name": "Mr. Rajesh Malhotra",
         "address": "Director, M/s Highway Auto Spares Private Limited, 14, Industrial Area Phase II, Chandigarh – 160002"},
        {"name": "Mrs. Simran Malhotra",
         "address": "Director, M/s Highway Auto Spares Private Limited, 14, Industrial Area Phase II, Chandigarh – 160002"},
    ],
    mode="BY SPEED POST", signatory_name="Meena Marar", signatory_desig="General Manager – Legal",
    authority_confirmed=True,
)

S138 = dict(HIGHWAY,
    business="Dealer of CEAT tyres since 2021, supplied on 30-day credit terms",
    background=("Invoice No. CEAT/CH/2026/0298 dated 28.05.2026 for supply of CEAT tyres and tubes on "
                "30-day credit terms to M/s Highway Auto Spares Private Limited, against which Cheque No. "
                "004521 dated 05.06.2026 for INR 2,00,000/- was issued towards part-discharge of the "
                "invoice dues."),
    invoices=[{"no": "CEAT/CH/2026/0298", "date": "2026-05-28", "amt": "448000"}],
    cheques=[{"no": "004521", "date": "2026-06-05", "amt": "200000",
              "bank": "HDFC Bank, Sector 17 Branch, Chandigarh"}],
    presented_date="2026-06-10", dishonour_date="2026-06-14", dishonour_reason="Funds Insufficient",
    memo_date="2026-06-14",
    part_payment=("No further part-payment has been made after issuance of the dishonoured cheque. Amount "
                  "demanded under this notice is limited to the dishonoured cheque amount of INR 2,00,000/-."),
    amount="448000",                      # what the old analysis step produced
    jurisdiction="Mumbai", notice_date="2026-06-20", prior="No",
)

RECOVERY = dict(HIGHWAY,
    relationship=("Appointed as an authorised dealer of CEAT in 2021 for supply of tyres, tubes and flaps, "
                  "supplied on a running account on 30-day credit terms."),
    soa=[{"ref": "CEAT/CH/2026/0298", "date": "2026-05-28", "amt": "448000"},
         {"ref": "CEAT/CH/2026/0355", "date": "2026-06-10", "amt": "200000"},
         {"ref": "CEAT/CH/2026/0402", "date": "2026-06-22", "amt": "195000"},
         {"ref": "CEAT/CH/2026/0448", "date": "2026-07-05", "amt": "231500"},
         {"ref": "CEAT/CH/2026/0501", "date": "2026-07-18", "amt": "148000"}],
    amount="1222500", as_on_date="2026-07-18", interest="8", notice_date="2026-08-01",
    prior="",                             # was silently seeded "No"
)

CONSUMER = dict(
    incoming="1. ...\n2. ...\n3. ...\n4. ...\n5. ...\n6. ...\n7. ...\n8. ...",
    advocate_name="Rajiv Mehta",
    advocate_address="Mehta & Associates, Advocates & Legal Consultants, 402, Sun Plaza, Ashram Road, Ahmedabad – 380009, Gujarat",
    notice_date="2026-09-21",             # today's date, seeded by the old default
    reply_date="2026-09-21",
    client_name="CEAT Limited",           # what the old model call returned
    client_relation="Manufacturer of CEAT SecuraDrive tyres referred to in the notice",
    client_address="RPG House, 463 Dr. Annie Besant Road, Worli, Mumbai – 400030",
    product="CEAT SecuraDrive tyres size 205/55 R16",
    dealer="M/s Sterling Tyre World, 18, Ashram Road, Ahmedabad – 380009, Gujarat",
    claim_date="2026-07-18", inspection="",
    paras=[
        {"n": "1", "stance": "Deny", "text": "The contents of paragraph 1 of the legal notice, to the extent they merely state that the notice issuer is the registered owner of vehicle bearing registration no. GJ-01-RK-4567, are a matter of record and do not call for any response from CEAT Limited. Save as aforesaid, the remaining allegations are denied."},
        {"n": "2", "stance": "Deny", "text": "With reference to paragraph 2, it is not disputed, based on the dealer invoice enclosed with the notice, that four CEAT SecuraDrive tyres (size 205/55 R16) were sold on 05.03.2026 by M/s Sterling Tyre World, Ahmedabad, an authorised dealer, under Tax Invoice No. STW/2026/1184."},
        {"n": "3", "stance": "Deny", "text": "The contents of paragraph 3 are specifically denied. It is denied that any representation was made that the tyres would deliver a minimum tread life of 40000 km."},
        {"n": "4", "stance": "Deny", "text": "It is specifically denied that the tyres developed any manufacturing defect."},
        {"n": "5", "stance": "Deny", "text": "Any warranty claim is subject to inspection strictly in accordance with CEAT's warranty policy."},
        {"n": "6", "stance": "Deny", "text": "It is denied that there is any deficiency in service or unfair trade practice."},
        {"n": "7", "stance": "Deny", "text": "It is denied that the notice issuer was compelled to purchase a replacement set of tyres for 30000."},
        {"n": "8", "stance": "Deny", "text": "The demands for (a) replacement or refund of 32000, (b) 30000, (c) 150000 and (d) 20000 are unjustified and denied."},
    ],
    demands=[{"d": "Replace four tyres free of cost or refund 32000", "resp": "Denied"},
             {"d": "Reimburse 30000 allegedly spent on replacement set", "resp": "Denied"},
             {"d": "Pay 150000 towards compensation", "resp": "Denied"},
             {"d": "Pay 20000 towards cost of legal notice", "resp": "Denied"}],
    signatory_name="Meena Marar", signatory_desig="General Manager – Legal", authority_confirmed=True,
    blk_a=True, blk_b=True, blk_c=True,
)

BREACH = dict(
    noticee_type="Individual / sole proprietor",
    noticee_name="M/s Deccan Auto Tyres", firm_name="M/s Deccan Auto Tyres",
    noticee_address="Plot 12, Market Yard Road, Pune – 411037, Maharashtra",
    agreement_name="Dealership Agreement", agreement_date="2024-04-01", clause_no="9.1, 9.2 and 18.1",
    obligation=("Timely payment of all invoices for Products supplied within 30 (thirty) days from the date of "
                "the respective invoice, and payment of interest at 8% (eight per cent) per annum on any amount "
                "outstanding beyond the agreed credit period, as per Clause 9.1 and Clause 9.2 of the "
                "Dealership Agreement."),
    breach_facts=("Under the Dealership Agreement dated 1 April 2024, you are required to make payment for all "
                  "Products supplied within 30 (thirty) days from the date of the respective invoice (Clause "
                  "9.1). Notwithstanding repeated reminders, you have failed to clear the outstanding dues on "
                  "your running account.\nAs per the Company's records as on 25.08.2026, the following invoices "
                  "remain unpaid and are overdue:\n• Invoice CEAT/PN/2026/0451 dated 18.05.2026, outstanding "
                  "amount INR 284000.00.\n• Invoice CEAT/PN/2026/0489 dated 02.06.2026, outstanding amount INR "
                  "196500.00.\n• Invoice CEAT/PN/2026/0533 dated 21.06.2026, outstanding amount INR 310000.00.\n"
                  "The total outstanding on your account is INR 790500.00 as on 25.08.2026."),
    cure_period="15 (FIFTEEN) days",
    consequences=("If you fail to cure the aforesaid breach by paying the entire outstanding dues together with "
                  "applicable interest within the Cure Period, the Company shall be entitled, without prejudice "
                  "to its other rights and remedies under the Dealership Agreement and applicable law, to "
                  "terminate the Dealership Agreement for cause in accordance with Clause 19.1 and to initiate "
                  "appropriate legal proceedings for recovery of all amounts due along with interest, costs and "
                  "consequential losses."),
    mode="BY SPEED POST", signatory_name="Meena Marar", signatory_desig="General Manager – Legal",
    notice_date="2026-09-21", prior="No",
)


# ---- the same matters after the user corrects what the checks asked for ----
S138_FIXED = dict(S138, amount="200000", part_paid="0",
                  background="Appointed as an authorised dealer of CEAT in 2021 for tyres, tubes and flaps on "
                             "30-day credit terms.")
RECOVERY_FIXED = dict(RECOVERY, notice_date="2026-09-01", as_on_date="2026-08-25",
                      interest_from="from the due date of each invoice", prior="Yes",
                      prior_date="2026-06-20",
                      prior_ref="dishonoured cheque no. 004521 dated 05.06.2026 for INR 2,00,000/- issued "
                                "against invoice CEAT/CH/2026/0298")
CONSUMER_FIXED = dict(CONSUMER, client_name="Mr. Prakash Desai", client_relation="owner of vehicle GJ-01-RK-4567",
                      client_address="27, Shivalik Bungalows, Satellite Road, Ahmedabad – 380015",
                      notice_date="2026-07-28", reply_date="2026-09-08", dealer_authorised="Not sure",
                      inspection="to have uneven wear consistent with under-inflation, not a manufacturing defect")
BREACH_FIXED = dict(BREACH, noticee_name="Mr. Sanjay Kulkarni", clause_no="9.1 and 9.2",
                    authority_confirmed=True)
