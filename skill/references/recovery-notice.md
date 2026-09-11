# Recovery Notice (Demand for Outstanding Dues)

A demand notice for recovery of outstanding dues/arrears owed to CEAT on unpaid invoices
(no dishonoured cheque involved). Demands the outstanding sum **plus interest @ 8% p.a.**,
payable within **10 days**.

## When to use
A dealer/customer has received Goods against invoices, has not paid despite follow-ups,
and CEAT wants to formally demand payment before initiating civil/criminal proceedings.

## Required inputs (ask for any that are missing)
- Noticee type: individual/sole proprietor **or** company + directors (+ director names)
- Noticee name(s), address(es), and contact (email/WhatsApp) if to be shown
- Nature of dealing (dealership / fleet services / supply) — brief
- Outstanding amount (figures and words), and the **as-on date**
- Interest rate (default **8% p.a.** unless the user specifies otherwise)
- Invoice details for the statement of account (long form): SR no., invoice/reference
  number, document date, outstanding amount — and the total
- Payment-terms basis (e.g., payment due within 30 days of invoice)
- Demand period (default **10 days**), signatory
- Place of jurisdiction / where a complaint would be filed if unresolved — default to
  CEAT's registered office unless the user specifies otherwise
- If invoices are tax-inclusive: the breakup of principal vs. GST/tax component,
  so the demand states what the outstanding sum actually comprises

## Refusing an approximate demand figure
A recovery notice must state an exact sum, as on a specific date, in both figures and
words — a demand for "around ₹3,20,000" or similar is not draftable as-is. If the user
gives only an approximate figure, ask for an invoice-wise breakdown (or at minimum the
exact total as on a stated date) before drafting; don't round, estimate, or draft around
the approximation.

## Handling a partial payment already received
If the user mentions a payment received against the outstanding amount:
- If they give you the net balance directly, use it.
- If they only give you the original invoice amount and the payment amount, you may
  compute the net balance yourself — but show the arithmetic in chat and explicitly ask
  the user to confirm no further receipts or credit notes exist since the last payment
  date before treating the computed figure as final. Never silently net it off inside
  the document without disclosing that a computation was made.

## Variants
- **Long form** → multiple outstanding invoices: include the **Statement of Account
  table** and the fuller set of paragraphs.
- **Short form** → a single/simple sum: omit the table; use the condensed paragraphs.
- **Individual vs company** noticee block as per `house-style.md`.

## Template (long form; drop the table and bracketed paras for short form)

```
{{LETTERHEAD}}                    (see house-style.md)

THROUGH SPEED POST / EMAIL / WHATSAPP

WITHOUT PREJUDICE

To,                                {{DATE}}
{{NOTICEE_BLOCK}}

Sub: Demand notice for recovery of dues amounting to INR {{AMOUNT_FIGURES}}
({{AMOUNT_WORDS}}) along with interest @ {{INTEREST_RATE}}% p.a.

Sir/Madam,

1. CEAT Limited ("the Company") is a Public Limited Company duly incorporated under the
   provisions of the Companies Act, 1956, having its Registered Office at 463, Dr. Annie
   Besant Road, Worli, Mumbai – 400030.

2. The Company deals in the business of manufacture and sale of Tyres, Tubes and Flaps
   (hereinafter referred to as the "Said Materials").

3. {{RELATIONSHIP_PARA}}   (how the dealing arose — you approached the Company and
   obtained dealership / submitted a proposal for supply of the Said Materials, which
   the Company accepted. For a company noticee, describe Noticee 1 and its directors.)

4. That in the course of business and against orders placed by you, the Company sold,
   supplied and delivered the Said Materials from time to time, duly received,
   acknowledged and accepted by you without demur as to quality and/or quantity.

5. Towards the supply, the Company raised various invoices and maintained a running and
   continuous account of your transactions reflecting the amounts due and payable.

6. The Said Materials were received by you in full satisfaction, and you were liable to
   pay the invoice amounts, the Company having supplied on the assurance of payment
   within 30 days from the date of invoice. However, you have failed to pay the
   outstanding invoices.

7. As per the Company's records, as on {{AS_ON_DATE}} a total outstanding amount of INR
   {{AMOUNT_FIGURES}} ({{AMOUNT_WORDS}}) is pending from you towards the Said Materials
   supplied. The Statement of Account is as follows:

   {{STATEMENT_OF_ACCOUNT_TABLE}}   (SR No. | Invoice/Reference | Document Date |
   Outstanding Amount; end with the Total.)

8. Despite the Company's vigorous follow-ups, you have failed to make payment as per the
   agreed terms and conditions.

9. As per the agreed terms of the invoices, you are liable and duty-bound to pay the
   outstanding amount of INR {{AMOUNT_FIGURES}} ({{AMOUNT_WORDS}}) as on {{AS_ON_DATE}}.

{{AMOUNT_BREAKUP_PARA}}   (optional — include ONLY if the user supplied a principal/GST
   breakup for a tax-inclusive invoice; use the "Amount breakup (principal + tax)" block
   from `clause-library.md`. The figures here MUST sum exactly to {{AMOUNT_FIGURES}} in
   paragraph 9 — if they don't, stop and flag the discrepancy to the user rather than
   drafting either figure. If no breakup was supplied, omit this paragraph entirely.)

10. You received the Said Materials as per your requirement and yet failed to pay,
    demonstrating a false and fraudulent intention from the beginning. Your acts and
    conduct are patently illegal, untenable and contrary to settled principles of law.

11. In the aforesaid circumstances, the Company hereby calls upon you to pay the
    aforesaid sum of INR {{AMOUNT_FIGURES}} ({{AMOUNT_WORDS}}) along with interest @
    {{INTEREST_RATE}}% p.a.

12. Through your deliberate and wilful actions you have deceived and cheated the Company,
    attracting the penal provisions of Sections 316(2) and 318(4) of the Bharatiya Nyaya
    Sanhita, 2023, causing wrongful loss to the Company and wrongful gain to yourself.

13. In case you fail to pay the aforesaid amount within 10 days from the date of receipt
    of this notice, the Company will initiate appropriate legal proceedings, civil as
    well as criminal, against you at your entire risk as to costs and consequences.

{{JURISDICTION_PARA}}   (optional — include ONLY if a place of jurisdiction was supplied
or defaulted per "Required inputs" above; use the "Jurisdiction / place of proceedings"
block from `clause-library.md`, filling {{JURISDICTION_PLACE}}. If none was supplied or
defaulted, omit this paragraph entirely — do not insert a jurisdiction clause with no
place named, and do not invent a place.)

Yours faithfully,
For CEAT Limited
{{SIGNATORY_BLOCK}}
```

## Mandatory validation checklist (run before delivering)
- [ ] Subject states the recovery amount (figures + words) and the interest rate.
- [ ] Outstanding amount stated with an **as-on date**, consistent throughout.
- [ ] Long form: Statement of Account table present with a **Total** that ties to the
      demanded amount. (If the table total and the demanded figure differ, flag it.)
- [ ] Interest @ **8% p.a.** stated (or the rate the user specified).
- [ ] Demand gives **10 days** from receipt.
- [ ] BNS Sections **316(2)** and **318(4)** referenced (and 2(36)/2(37) if used).
- [ ] Civil **and** criminal proceedings language present.
- [ ] If a principal/GST breakup was supplied, the breakup paragraph appears in the
      drafted text and its components sum exactly to the demanded figure — if they don't
      tie out, drafting stopped and the discrepancy was raised with the user, not guessed.
- [ ] If a jurisdiction was supplied or defaulted, the Jurisdiction paragraph actually
      appears in the drafted text (not just recorded as a fact) — and is omitted
      entirely if no place was supplied.
- [ ] If the outstanding figure was netted from a partial payment, the arithmetic was
      shown and confirmed with the user — not silently assumed.
- [ ] Review banner appended.
