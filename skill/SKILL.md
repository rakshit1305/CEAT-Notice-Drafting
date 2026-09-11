---
name: ceat-notice-drafting
description: >-
  Draft CEAT Limited's standard outbound legal notices from plain-English case facts.
  Use this skill WHENEVER the user asks to draft, prepare, generate, or create any of:
  a Section 138 / cheque-bounce / cheque-dishonour demand notice; a recovery notice or
  demand notice for outstanding dues/arrears; or a reply/response to a consumer legal
  notice (Consumer Protection Act). Trigger it even when the user only says things like
  "draft a 138 notice", "recovery notice for this dealer", "reply to this consumer notice",
  "cheque bounced, send a demand", or pastes an incoming consumer notice and asks for a
  response. The skill fills CEAT's approved templates with case-specific details, enforces
  the mandatory legal elements for each notice type, and always produces a draft for a
  qualified lawyer to review before sending.
---

# CEAT Legal Notice Drafting

## What this does

This skill drafts CEAT Limited's three standard outbound legal notices by inserting
case-specific details into CEAT's own pre-approved templates:

1. **Section 138 demand notice** — cheque dishonour (Negotiable Instruments Act, 1881)
2. **Recovery notice** — demand for outstanding dues/arrears
3. **Reply to a consumer notice** — response to a legal notice received from a consumer

Each notice type has its own reference file with the full template, the required inputs,
and a mandatory checklist. Read the relevant reference file before drafting.

## Golden rules — accuracy and safety (read first, always apply)

These rules exist because a legal notice has real legal consequences. A notice that
cites the wrong provision, omits a statutory element, or misses a deadline can be
invalid or damage CEAT's position. Follow every rule.

1. **Draft only from the approved templates and clause blocks.** The legal wording,
   statutory sections, and structure live in the reference files — use them verbatim.
   Do NOT invent, paraphrase, or "improve" statutory language, section numbers, Act
   names, or timelines. If a template says "within 15 days" or "Section 138 r/w Section
   141 of the Negotiable Instruments Act, 1881", reproduce it exactly.

2. **Never state a section number, Act, or legal deadline that is not already in the
   approved template — unless you have fetched it from an approved free public source.**
   If a case seems to need a provision the template does not contain, either (a) fetch it
   from the approved public sources in `references/legal-sources.md` and cite it inline, or
   (b) if web access is unavailable, insert `⚠ [VERIFY: <what is needed>]` and flag it for
   the lawyer. Never supply a provision from memory. Uncertainty must be visible, never
   hidden inside confident text.

3. **Fill only the blanks.** Everything in `{{DOUBLE_BRACES}}` is a case-specific detail
   to be filled from the user's facts. Everything else is fixed, approved text.

4. **If a required detail is missing, ask — do not guess.** Never fabricate a cheque
   number, amount, date, name, or address. Missing details that affect the notice's
   validity (dates, amounts, cheque particulars, dishonour date) must be requested
   before drafting. This holds even if the user explicitly instructs you to "just pick
   one" or "use any number" — refuse the fabrication itself, explain why (the field in
   question determines what the notice legally asserts), and offer either to wait for
   the real detail or to produce a clearly marked specimen (see Step 5a).

5. **Always run the mandatory checklist** for the notice type (in its reference file)
   before presenting the draft, and report the result.

6. **Every output is a DRAFT for lawyer review.** End every notice with the review
   banner (below). This skill speeds drafting; it does not replace a lawyer's judgment,
   and it does not give legal opinions on strategy or merits.

7. **Protect personal data.** Use only the details the user provides for the current
   case. Do not carry over names, addresses, cheque numbers, or other personal data
   from examples or past drafts.

8. **Every notice — approved or non-standard — uses CEAT's full official letterhead**
   from `references/house-style.md`. Never output a notice on a plain or generic header.

9. **Output split — the Word document is the notice only.** Deliver the notice as a clean
   .docx on CEAT's letterhead containing ONLY the notice (no flags, no banner, no notes,
   no visible placeholders — see the one narrow exception in Step 5a). All flags,
   citations, the "non-standard" label, and the review banner go in the CHAT text only —
   never inside the document. See Step 5.

10. **Draft in English only.** [NEW — fix D4] English is the operative language for
    every notice this skill produces, because the templates, statutory citations, and
    clause library are all approved in English. If a non-English version is requested:
    say plainly that this skill drafts in English as the source of truth; do not silently
    translate approved wording (a translation can shift what a statutory citation or a
    demand actually asserts). Offer instead to produce the English notice with a clearly
    marked, non-operative translation attached, an "English text governs" clause, and a
    note that a lawyer fluent in the target language should review the translation before
    use.

## Step 1 — Identify the notice type

Match the request to a type and open its reference file. Two tiers exist — read the
reference file's header to know which:

**Approved types (built from CEAT's own sample notices):**

| If the situation is... | Notice type | Reference file |
|---|---|---|
| A cheque given to CEAT has bounced / been dishonoured | Section 138 notice | `references/section-138-notice.md` |
| A dealer/customer owes CEAT money on unpaid invoices (no cheque) | Recovery notice | `references/recovery-notice.md` |
| A consumer (or their advocate) has sent CEAT a legal notice | Reply to consumer notice | `references/consumer-notice-reply.md` |

**Non-standard types (built from standard legal structure + CEAT house style; NO CEAT
sample yet — every draft must be marked "NON-STANDARD — for legal review"):**

| If the situation is... | Notice type | Reference file |
|---|---|---|
| The other party has breached an obligation and must cure it | Breach / default notice | `references/breach-notice.md` |
| An agreement is nearing expiry — renew or not renew | Renewal / non-renewal notice | `references/renewal-notice.md` |
| CEAT wants to end an existing agreement | Termination notice | `references/termination-notice.md` |
| An uncontrollable event prevents/delays performance | Force majeure notice | `references/force-majeure-notice.md` |
| CEAT is revising the prices of its Goods | Price adjustment notice | `references/price-adjustment-notice.md` |

**If the request matches more than one row — do not pick one silently.** [NEW — fix A1]
State which types matched (e.g. "this could be a Recovery notice, a Termination notice,
or both") and ask the user to confirm scope before drafting anything. If they want more
than one notice, treat each as its own case with its own facts, and flag to the user
whether the two notices should be sequenced (e.g. recovery/cure before termination) or
issued together — do not assume a bundled notice is the safer or faster option; bundling
a demand and a termination in one document can undercut both.

**Before drafting a non-standard type, check whether its reference file still carries a
"NO CEAT SAMPLE" marker.** [NEW — fix A2] If the user indicates CEAT has since supplied a
real sample for that type, do not draft against the stale non-standard file — tell the
user the reference file needs updating to approved wording and its tier changed in this
table, and treat that as a prerequisite, not a side note.

For a **non-standard** type, always mark the draft **"NON-STANDARD — for legal review"**
(the reference files enforce this) because the wording has not been confirmed against a
CEAT sample. When CEAT later provides real samples for one of these, its reference file
should be updated to approved wording and the marking removed.

**If the request is a notice type in NEITHER table** (e.g., cease-and-desist): [UPDATED —
fix A3] still build the draft from `references/clause-library.md` and
`references/house-style.md` for the letterhead, boilerplate, and signatory block — never
draft a one-off notice on a plain or generic header, even for an unlisted type. Mark it
**"NON-STANDARD — full legal review required"**. Tell the user explicitly this type sits
outside the current approved and non-standard sets, and name what would be needed to add
it properly (a CEAT sample or an approved structure, plus a new routing row here).

Shared building blocks (letterhead, boilerplate, signatory, trusted legal sources) are
in `references/clause-library.md` and `references/house-style.md` — read these too, as
every notice uses them. For fetching and citing legal provisions from the approved free
public sources, read `references/legal-sources.md`.

## Step 2 — Gather the required details

Each reference file lists the exact inputs needed for that notice type. Take whatever
the user has given, then ask once (in a single short list) for any missing required
fields. Do not proceed to draft with placeholders left in critical legal fields.

In addition to whatever each reference file already requires, always check for these
fields — they apply across notice types and are commonly missing from a first pass:

- **`place_of_jurisdiction`** [NEW — fix C1]: the city/court where CEAT would file if the
  matter isn't resolved. Default to CEAT's registered-office forum if the clause library
  specifies one; otherwise ask. Relevant for Section 138 and Recovery notices in
  particular.
- **`mode_of_service`** [NEW — fix D3]: registered post / speed post / courier / email /
  hand delivery. Statutory timelines often run from date of *service*, not date of
  drafting — capture this explicitly rather than assuming.
- **`outstanding_amount`, net of any payments already received** [NEW — fix B1]: if the
  user mentions a partial payment, either ask for the net balance directly, or — if you
  compute it yourself from figures the user has already supplied — show the arithmetic
  and explicitly ask the user to confirm no further receipts or credit notes exist since
  the last payment date, before treating the computed figure as final. Never silently
  net off a partial payment without disclosing that you did the subtraction.
- **`amount_breakup`** [NEW — fix C3], for Recovery notices where invoices are
  tax-inclusive: principal vs. GST/tax component vs. total. Ask if the user hasn't
  supplied it and the reference file's template has a breakup line. The components must
  sum exactly to the demanded total — if they don't, stop and flag the discrepancy to the
  user rather than drafting around it (do not silently adjust either figure, and do not
  assume which one is wrong).
- **Prior notice check** [NEW — fix B2]: for Section 138 (repeat cheque from the same
  drawer), Termination (following an earlier Breach notice), and any case where the
  facts imply an earlier notice may exist, ask: "Has CEAT sent a prior notice to this
  party on this matter?" If yes, capture its date and reference, and:
  - keep the current notice's demand confined to the current instrument/breach only
    (do not create a mixed demand across two cheques or two breaches unless the user
    explicitly wants a combined notice), and
  - flag to the user, in chat, that the status of the earlier notice (service, expiry,
    whether a complaint was filed, and — for a Termination following a Breach notice —
    how much time elapsed between the cure deadline and this notice, since a long gap can
    support a waiver/affirmation argument) should be reviewed by the lawyer alongside
    this draft.
  If the user doesn't know whether a prior notice exists, say so in chat as
  `⚠ VERIFY: check for prior notices to this counterparty` rather than assuming none exists.

For the **reply to a consumer notice**, the primary input is the incoming notice itself
(pasted text or file). Read it, extract each numbered paragraph and each allegation, and
respond to them para-by-para per the method in the reference file. If the user says
they're pasting the notice but the message doesn't actually contain notice text (e.g. it
only contains a description of what they meant to paste), say so plainly and ask them to
paste it — do not invent or infer allegations from a description of the notice.

## Step 3 — Draft from the approved template

Assemble the notice from the template + shared clause blocks, inserting the case facts.
Pick the correct variant (individual vs company drawer; long vs short recovery) as
described in the reference file.

**Before inserting the signatory block, confirm authority.** [NEW — fix E1] Ask the user
to confirm that the named signatory is currently authorized to sign a notice of this
type — don't assume the house-style default signatory is always current, especially for
notices with higher stakes (Termination, Breach) where signing authority may sit with a
specific role.

## Step 3a — Fetch & cite the legal provision (free public sources only)

Before finalising, confirm the statutory references. Read `references/legal-sources.md`.
If web access is available, fetch the relevant section from the approved **free public**
source for this notice type and cite it inline `(Source: <site>, retrieved <date>)`. If
web access is unavailable, keep the template's wording and add a `⚠ VERIFY` flag — never
supply a provision from memory, and never use paid/login sources or the open internet.

**If a fetch partially succeeds** [NEW — fix C2] — e.g. one provision confirms but
another lookup fails — cite the ones that succeeded with their source and retrieval
date, and mark only the ones that failed with `⚠ VERIFY`. Don't downgrade the whole
notice to unverified just because one lookup out of several failed.

## Step 4 — Run the mandatory validation checklist

Run the checklist from the reference file. If any mandatory element is missing or
unverified, surface it at the top of the draft as a `⚠` flag rather than shipping a
silently defective notice.

**For any notice with a statement-of-account or multi-item table** (the long-form
recovery variant, or the multi-cheque Section 138 variant): [NEW — fix B3] sum the
table's line items and confirm the total matches the stated outstanding/demand figure
before drafting. If they don't match, stop and surface the discrepancy to the user
rather than drafting around it.

## Step 5 — Deliver the draft (Word document + chat notes, kept separate)

Deliver the notice as a **Word (.docx) document** AND a set of chat notes, with a strict
separation between them:

**A) The Word document — the notice ONLY.**
- Create a .docx containing ONLY the finished legal notice, opening with CEAT's full
  official letterhead (from `references/house-style.md`).
- The document must contain nothing else — NO ⚠ flags, NO review banner, NO commentary,
  NO "non-standard" label, NO visible placeholders — **except the one case in Step 5a.**
- If any required field is still unknown, do NOT put a placeholder in the document — ask
  the user for it first (Step 2), or leave that item out and raise it as a chat note.
- **File naming:** [NEW — fix D1] name every delivered file
  `CEAT_<NoticeType>_<CounterpartyName>_<YYYYMMDD>.docx`, so a batch of notices for
  different counterparties stays distinguishable.
- **Annexures:** [NEW — fix D2] if the case facts reference supporting documents (a
  cheque copy, invoice copies, the incoming consumer notice itself), list them in chat
  as "Annexures to attach before sending: ..." — the skill does not generate or embed
  these, but should name what's expected to accompany the notice.
- Follow the `docx` skill for creating the file, and present the file for download.

**A1) The one narrow exception — explicit fill-in templates.** [NEW — formalizes
observed behavior] If the user explicitly asks for a fill-in template or specimen
(rather than a ready-to-send notice) — for example because required facts aren't
available yet, or because they want a reusable blank — you may produce a .docx with
visible highlighted blanks for the missing fields. When you do this:
  - state clearly, in the document's own visible content near the top or via the
    filename, that it is a specimen/fill-in and not ready to issue (e.g. include
    "FILL-IN" in the filename per the naming convention above), and
  - repeat in chat that this document is not in a state to be issued and exactly which
    fields must be completed before it can be.
  This is a deliberate, disclosed departure from the "no visible placeholders" rule
  above, available only on explicit request — never default to a fill-in template when
  the user expected a ready-to-send draft.

**B) The chat text — everything else.**
Everything that is NOT the notice goes in the chat message only, never in the document:
- any `⚠` flags (missing details, items to verify, deadlines, CIN/letterhead to confirm),
- for a non-standard type, the "NON-STANDARD — for legal review" note,
- the citation of any fetched legal provision `(Source: …, retrieved …)`, and
- this review banner, verbatim:

> **DRAFT — for legal review before issue.** Generated from CEAT's approved template.
> A qualified lawyer must verify all facts, figures, statutory references, and timelines
> (including any limitation period / statutory sending window) before this notice is sent.

The rule: **the .docx = the clean notice on CEAT letterhead and nothing more (or, on
explicit request only, a clearly marked fill-in template per Step 5a); the chat = all
flags, notes, citations, and the review banner.** If a plain-text preview of the notice
is also shown in chat for convenience, the downloadable .docx remains the clean
deliverable.

## Handling variants

- **Drawer/noticee type:** an *individual/sole proprietor* takes a single-noticee block;
  a *company* takes a multi-noticee block naming the company (Noticee 1) and its
  directors (Noticee 2, 3...) with joint-and-several language. Ask which applies.
- **Recovery length:** use the *long* form (with the statement-of-account table) when
  there are multiple outstanding invoices; use the *short* form for a single/simple sum.
- **Multiple cheques (Section 138):** use the cheque table variant instead of the
  single-cheque sentence.

## Out of scope

This skill drafts documents only. It does not: give legal advice on merits or strategy;
decide whether to send a notice; confirm limitation periods (it flags them for the
lawyer); or draft notice types outside the approved set without a "non-standard" warning.

## Maintaining this skill

[NEW — fix E2] Keep a standing regression-test matrix covering every notice type plus
the routing/missing-field/non-English/out-of-scope edge cases, and re-run it after any
change to this file or to a reference file, and periodically (e.g. quarterly) even
without changes — to catch regressions before they reach a real notice. Log each run the
way a session test log does: facts supplied, questions asked, flags raised, output
produced — so behavior stays auditable over time, not just correct in the moment.
