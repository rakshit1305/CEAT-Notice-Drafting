# Section 138 Demand Notice (Cheque Dishonour)

Legal notice under **Section 138 read with Section 141 of the Negotiable Instruments
Act, 1881**, issued when a cheque given to CEAT has been dishonoured.

## When to use
A cheque (or cheques) issued to CEAT towards an admitted liability has been returned
unpaid by the bank (e.g., "Funds Insufficient"). CEAT demands the cheque amount within
15 days, failing which it will initiate proceedings.

## Critical timing (flag for the lawyer — do not decide this yourself)
The statutory scheme is time-bound. The demand notice must be sent within the statutory
window after CEAT receives the bank's dishonour memo, and the drawer must be given the
statutory period to pay. Always add this flag to the draft:
`⚠ [VERIFY: notice is being sent within the statutory period from the date of the bank
dishonour memo ({{DISHONOUR_MEMO_DATE}}), and the 15-day demand period is correct for this case.]`

## Required inputs (ask for any that are missing)
- Drawer type: individual/sole proprietor **or** company + directors
- Noticee name(s) and address(es); for a company, the directors' names
- Nature of dealing (dealership / purchase order / supply) — brief
- Invoice/PO details: number(s), date(s), amount(s)
- Cheque particulars: cheque number, cheque date, amount, drawn-on bank (and branch)
- Presentation & dishonour: date presented, dishonour date, reason on memo, bank memo date
- Any part-payments already made, and the resulting balance now demanded
- Amount demanded (in figures and words)
- Mode of sending; signatory name and designation
- Place of jurisdiction / where a complaint would be filed if unresolved — default to
  where the cheque was presented for payment or CEAT's registered office if the user
  doesn't specify; ask rather than assume if genuinely unclear
- Whether CEAT has sent a **prior Section 138 notice to the same drawer** on a different
  cheque (see "Repeat cheque from the same drawer" below)

## Refusing fabrication (apply strictly)
Cheque number and dishonour date are not cosmetic details — the cheque number identifies
the instrument the offence attaches to, and the dishonour date sets the statutory clock.
If the user asks you to "just pick one," use a placeholder number, or invent a plausible
date, decline and explain why. Offer instead to either (a) wait for the real particulars,
or (b) produce a **specimen** clearly marked `SPECIMEN — NOT FOR ISSUE` in the filename
and disclosed as such in chat — never a document that looks ready to send.

## Repeat cheque from the same drawer
If this is a second (or further) cheque from a drawer CEAT has already sent a Section
138 notice to:
- Confine this notice's demand to the new cheque's amount only — do not combine it with
  the earlier cheque's amount into one mixed demand unless the user explicitly asks for
  a combined notice covering both.
- Flag in chat (not in the document) that the status of the earlier notice — whether it
  was served, whether the 15-day period has expired, whether a complaint has been filed
  — should be reviewed by the lawyer alongside this draft, since it may affect strategy
  (e.g., whether to file one complaint or two).

## Variants
- **Single cheque** → use the single-cheque sentence.
- **Multiple cheques** → replace with the cheque table.
- **Individual drawer** → single-noticee block, singular "you".
- **Company drawer** → multi-noticee block (company + directors), joint-and-several,
  and Section 141 (liability of directors) applies.

## Template

Use CEAT's letterhead and signatory from `house-style.md`. Fill every `{{...}}`.

```
{{DATE}}

{{MODE}}   (e.g., BY SPEED POST / EMAIL / WHATSAPP)

WITHOUT PREJUDICE

To,
{{NOTICEE_BLOCK}}          (see house-style.md — individual or company+directors)

Sub: Legal Notice u/s 138 r/w Section 141 of the Negotiable Instruments Act, 1881.

Sir/Madam,

We, CEAT Limited, having our Registered Office at 463, Dr. Annie Besant Road, Worli,
Mumbai – 400030, serve upon you the following notice:

1. That we are a Public Limited Company duly registered under the provisions of the
   Companies Act, 1956, having our registered office at the address mentioned above.
   We deal in the business of manufacture and sale of Tyres, Tubes and Flaps
   (hereinafter referred to as the "Goods").

2. {{NOTICEE_DESCRIPTION}}   (e.g., "That you are the sole proprietor and person in
   control and management of the proprietorship concern..." OR for a company: "That you
   Noticee No. 1 are a company registered in India engaged in {{BUSINESS}}, and Noticee
   Nos. 2 and 3 are its directors responsible for its management and day-to-day operations.")

3. {{TRANSACTION_BACKGROUND}}   (how the dealing arose — dealership / purchase order.)

4. That in the course of business and against orders placed by you, the Company sold,
   supplied and delivered the said Goods from time to time as per your requirements,
   which were duly received, acknowledged and accepted by you without demur as to
   quality and/or quantity.

5. That the Company supplied Goods vide the following invoice(s), received by you
   without complaint, against which you are liable to make payment:

   {{INVOICE_DETAILS}}   (Invoice No. | Invoice Date | Amount (INR))

6. That in discharge of your admitted liability you issued the following cheque(s):
   {{CHEQUE_DETAILS}}
   (single: "cheque no. {{CHEQUE_NO}} dated {{CHEQUE_DATE}} for INR {{CHEQUE_AMOUNT}}
   drawn on {{BANK_NAME}}", or use a cheque table for multiple cheques.)

7. That the aforesaid cheque(s) was/were presented for clearance and, to our shock,
   returned unpaid on {{DISHONOUR_DATE}} for the reason "{{DISHONOUR_REASON}}" vide bank
   memo dated {{DISHONOUR_MEMO_DATE}}.

8. {{PART_PAYMENT_PARA}}   (include only if part-payments were made; state amounts,
   dates, and the balance now outstanding. Otherwise omit.)

9. That despite our repeated efforts to contact you for payment of the balance amount
   against the dishonoured cheque(s), you have failed and neglected to pay, demonstrating
   your disregard for the consequences of non-payment.

10. That your conduct reveals an intention tainted with fraud. Prima facie you
    deliberately issued the aforesaid cheque(s) with knowledge that it/they would be
    dishonoured, thereby not only committing an offence under Section 138 of the
    Negotiable Instruments Act, 1881, but also criminal breach of trust punishable under
    Section 316(2) of the Bharatiya Nyaya Sanhita, 2023 ("BNS"), and cheating under
    Section 318(4) of the BNS.

11. Hence, through this notice, you are called upon to remit to the Company the entire
    legally enforceable debt of INR {{AMOUNT_DEMANDED_FIGURES}} ({{AMOUNT_DEMANDED_WORDS}})
    against the dishonoured cheque(s), within a period of 15 (FIFTEEN) days from the date
    of receipt of this notice, failing which the Company shall be constrained to initiate
    appropriate legal proceedings against you, for which you shall be solely responsible
    for the costs and consequences arising therefrom.

Please note that a copy of this notice has been retained by us for future reference.

{{JURISDICTION_PARA}}   (optional — include ONLY if a place of jurisdiction was supplied
or defaulted per "Required inputs" above; use the "Jurisdiction / place of proceedings"
block from `clause-library.md`, filling {{JURISDICTION_PLACE}}. If no jurisdiction was
supplied or defaulted, omit this paragraph entirely — do not insert a jurisdiction clause
with no place named, and do not invent a place.)

{{SIGNATORY_BLOCK}}
```

## Mandatory validation checklist (run before delivering)
- [ ] Subject cites **Section 138 r/w Section 141, NI Act, 1881** (verbatim).
- [ ] Cheque particulars present: number, date, amount, drawn-on bank.
- [ ] Dishonour date, reason, and **bank memo date** present.
- [ ] Amount demanded stated in **both figures and words**, and matches the balance
      after any part-payments.
- [ ] Demand gives **15 (FIFTEEN) days** from receipt.
- [ ] BNS Sections **316(2)** and **318(4)** referenced.
- [ ] For a company drawer: directors named as noticees; Section 141 applies.
- [ ] `⚠` timing flag added (statutory sending window vs bank-memo date).
- [ ] If a jurisdiction was supplied or defaulted, the Jurisdiction paragraph actually
      appears in the drafted text (not just recorded as a fact) — and is omitted
      entirely if no place was supplied.
- [ ] No cheque number, date, or other validity-critical detail was invented — every one
      came from the user or is flagged missing.
- [ ] If this is a repeat cheque from the same drawer: demand confined to this cheque
      only; earlier notice's status flagged to the lawyer, not assumed.
- [ ] Review banner appended.
