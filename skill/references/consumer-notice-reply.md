# Reply to a Consumer Notice

A response to a legal notice received from a consumer (or their advocate), typically
alleging deficiency in service / unfair trade practice under the Consumer Protection Act
over a tyre warranty claim. This is a **method**, not a simple fill-in: read the incoming
notice, then rebut it paragraph-by-paragraph using CEAT's standard defences.

## When to use
CEAT has received a consumer legal notice and needs to issue a reply that (a) denies the
allegations, (b) asserts CEAT's standard defences, and (c) answers the incoming notice
para-by-para.

## Primary input
The **incoming consumer notice** (pasted text or file). Also: the date of that notice,
the advocate's name/address, the client's details as stated, and any CEAT-side case
facts (e.g., whether/when a warranty claim was received, inspection findings, whether a
rejection letter was issued).

## Method (follow in order)
1. **Read the incoming notice.** Extract: the client's name and stated relationship to
   the product, the vehicle/product and dealer/OEM involved, each numbered paragraph, and
   every specific allegation and demand (e.g., replace tyre, pay legal charges). If the
   user says they're pasting the notice but the message doesn't actually contain notice
   text (only a description of what they meant to paste, or nothing at all), say so
   plainly and ask them to paste it — never invent or infer allegations from a
   description of the notice.
2. **Check for any point CEAT actually concedes.** Before applying the general denial,
   identify whether any specific paragraph states something CEAT's own facts confirm as
   true (e.g., a refund was approved but not yet processed). If so, that paragraph gets a
   specific, limited admission instead of a denial — the general denial in step 2 below
   still applies to everything else, but must not be worded to blanket-deny a point CEAT
   itself agrees with. A denial that a later-disclosed fact contradicts is a false
   statement in a signed legal document, and undermines the rest of the reply's
   credibility once that fact surfaces.
3. **Open with the general denial** (standard block below), scoped to exclude anything
   conceded under step 2.
4. **Insert the standard defence blocks** — business/principal-to-principal, warranty
   procedure, and no-privity — adapting the dealer/OEM names to this case. Omit any block
   that would contradict a conceded fact (e.g., don't assert no-privity if CEAT has
   already admitted a direct dealing or a direct refund obligation to this consumer).
5. **Respond para-by-para.** For each paragraph (or group) of the incoming notice, use
   the para-wise denial or admission formula as appropriate, and weave in CEAT's actual
   case facts where relevant (e.g., "we received the warranty claim on {{DATE}}; on
   inspection the tyre was found {{FINDING}}; hence not eligible under our warranty
   policy"). Every distinct allegation gets its own response — don't merge or drop
   paragraphs, even in a long or repetitive incoming notice.
6. **Deny the specific demands** that aren't conceded (replacement, refund, legal
   charges); for anything conceded in step 2, state what CEAT will actually do about it
   (e.g., process the refund now) rather than denying it.
7. **Close** with the standard closing block.
8. Run the checklist and append the review banner. Flag any admission made under step 2
   as a decision with legal consequences (it can be used in a subsequent complaint), not
   just a drafting choice — the lawyer should confirm before the reply is sent.

## Standard blocks (use CEAT's approved wording; adapt only the bracketed facts)

**Opening / general denial:**
> We, CEAT Limited ("Company"), are in receipt of the Said Notice dated {{NOTICE_DATE}}
> issued on behalf of your client {{CLIENT_NAME}}, {{CLIENT_RELATION}}, residing at
> {{CLIENT_ADDRESS}}. At the outset, the Said Notice is factually baseless, patently
> incorrect, mala fide and unsustainable under law. Unless specifically admitted, nothing
> in the Said Notice shall be deemed admitted or accepted by us. It also appears that your
> client has not properly apprised you of the facts.

**(A) Business / principal-to-principal:**
> We are engaged, inter alia, in manufacturing and marketing of tyres, tubes and flaps
> ("Products"). We sell our Products to our authorized dealers and to Original Equipment
> Manufacturers on a principal-to-principal basis. After such sale, we are not aware of
> onward sales by those dealers/OEMs to their customers/consumers.

**(B) Warranty procedure:**
> The Products are subject to the warranty obligations detailed on our Company website,
> along with the procedure to claim warranty. Our procedure requires the tyre(s)/tube(s)
> under claim to be submitted to the dealer/OEM/us for inspection; on receipt we issue a
> claim receipt, our Technical Service Engineer examines the item, and the disposition is
> communicated to the consumer with a copy of the inspection report. For sizes that
> cannot be transported, our Engineer may inspect at the consumer's premises if desired.

**(C) No privity of contract:**
> It is an admitted fact that your client has not purchased tyres from us or our
> authorized dealer. Your client purchased {{VEHICLE/PRODUCT}} from {{DEALER/OEM}}. We
> have no contractual, commercial or legal relationship with your client, who is
> admittedly not our direct customer. In the absence of privity of contract or other
> legal nexus, we neither owe any obligation nor bear any responsibility towards your
> client, and cannot be held liable for any representations or acts of {{DEALER/OEM}}.
> Any such claims lie solely against the parties who dealt directly with your client.

**Para-wise denial formula (repeat per paragraph):**
> With reference to para {{N}} of the Said Notice, we {{deny / are not aware of the
> averments and put your client to strict proof thereof}}. {{Case-specific response, if any.}}

**Closing:**
> Under such circumstances, notwithstanding the above, if your client initiates
> proceedings against us, kindly note that we shall have no alternative but to defend the
> same at your client's entire risk as to the costs and consequences thereof.

## Template (assemble from the blocks)

```
To,                                {{REPLY_DATE}}
{{ADVOCATE_NAME}}, Advocate
{{ADVOCATE_ADDRESS}}

Re: Your Notice dated {{NOTICE_DATE}} ("Said Notice")
Subject: Reply to your Said Notice.

Dear Sir/Madam,

{{OPENING_GENERAL_DENIAL}}

A) {{BUSINESS_PRINCIPAL_TO_PRINCIPAL}}
B) {{WARRANTY_PROCEDURE}}
C) {{NO_PRIVITY}}

Now, we respond para-wise to your Said Notice as follows:

{{PARA_WISE_RESPONSES}}      (one entry per paragraph/group of the incoming notice,
                             with CEAT's case facts woven in — e.g., inspection findings.)

{{DENY_SPECIFIC_DEMANDS}}    (replacement / refund / legal charges, as raised.)

{{CLOSING}}

Yours faithfully,
CEAT LIMITED

_________________
{{SIGNATORY_BLOCK}}
```

## Mandatory validation checklist (run before delivering)
- [ ] "Re:" line cites the incoming notice's **date**; subject = "Reply to your Said Notice".
- [ ] General-denial opening present ("unless specifically admitted, nothing... admitted").
- [ ] Standard blocks (A) principal-to-principal, (B) warranty procedure, (C) no-privity
      all present and adapted to the correct dealer/OEM/vehicle.
- [ ] **Every** numbered paragraph of the incoming notice is answered (none skipped).
- [ ] Each specific demand in the incoming notice is expressly denied.
- [ ] Any CEAT case facts stated (claim received date, inspection findings) match what
      the user provided — never invented. If not provided, flag `⚠ [VERIFY: inspection
      facts]` rather than inventing.
- [ ] No paragraph both denies and is contradicted by a fact CEAT has conceded elsewhere
      in the reply; any admission is flagged in chat as a legal decision for the lawyer.
- [ ] Standard closing present. Review banner appended.
