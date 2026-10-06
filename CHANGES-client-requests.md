# The six things CEAT asked for — what was built

All six are done and in the code. Every one has tests that fail if the change is
removed, so none of this is "should work".

Test suite: **238 passing** (169 before, 69 new).

---

## 1. Letterhead

**What CEAT asked:** letterhead to be shared by CEAT for use in the notices.

**What was there before:** the letterhead was typed text — name, address, Tel/CIN,
website — read out of `skill/references/house-style.md` and printed as three
paragraphs at the top of the first page of the document body. CEAT's actual
artwork had nowhere to go, and a notice running to two pages had nothing
identifying it on page 2.

**What was built.** Three ways to supply a letterhead, and the app uses the first
one it finds. All three are drop-in: **nothing in the code changes when CEAT's
file arrives.**

| Put this in `skill/assets/` | What happens |
|---|---|
| `letterhead.docx` | **Best.** CEAT's own Word template. Every notice is generated *inside* it, so the header artwork, footer, margins and fonts are theirs exactly. The template's placeholder body text is removed; its header, footer and page setup are kept. |
| `letterhead.png` (or `.jpg`) | The artwork, centred at the top of page 1, 16 cm wide by default. |
| *nothing* | The text block in `house-style.md` — what has been used until now. |

Three further changes came with it:

- The letterhead now sits in the **first-page header**, not in the body. Page 2
  onwards carries a slim `CEAT Limited — <subject>` running line instead of the
  whole letterhead repeated.
- Every page is numbered `Page n of m`, as a live Word field.
- An optional footer line for every page can be set in `house-style.md` under a
  `## Page footer` heading.

If the artwork cannot be read, the notice is still produced with the text
letterhead rather than with no letterhead at all.

**What CEAT needs to send:** their letterhead **as a .docx template** if one
exists — that is the strongest option, because nothing about their house layout
then has to be reproduced by hand. Otherwise a high-resolution PNG of the header
strip (1600–2400 px wide), plus any footer text. `skill/assets/README.md` spells
this out for whoever drops the file in.

---

## 2. Outlook emails taken as they are

**What CEAT asked:** Outlook emails to be taken directly as they are, without
being converted into a document format first, so no time is lost preparing the
input.

**What was there before:** the uploader accepted Excel, CSV, PDF, Word, text and
images. `.msg` and `.eml` were rejected. Someone had to open the mail, copy the
body into a text box or save it as a Word file, then save the attachment
separately and upload that too — which is exactly the preparation time CEAT was
describing.

**What was built.** Drag the mail straight out of Outlook. The app reads:

- **`.eml`** — standard MIME, read with Python's own library.
- **`.msg`** — Outlook's own format. This is a Compound File holding MAPI
  property streams; the app opens it with `olefile` (pure Python, added to
  `requirements.txt`, no build step, so it installs cleanly on Streamlit Cloud).

From either one it takes the headers (From / To / Cc / Date / Subject, with the
date in DD.MM.YYYY like everything else in the app), the body, and the quoted
reply chain underneath — **the chain is kept on purpose**, because in a dispute
the invoice number and the date the dealer admitted the dues are usually three
replies down.

**The part that actually saves the time:** the mail's **attachments are pulled
out and read as documents of their own**. A dealer's mail with the ledger
attached gives up both the mail and the ledger in one drag. Each attachment
appears in the app named `ledger.csv (attached to dealer mail)`.

Also handled:

- A ledger pasted into the body as an HTML table is flattened to `a | b | c`
  rows the analyser can read, instead of a smear of numbers.
- Confidentiality footers, "Sent from my iPhone", and `[cid:image001.png]`
  placeholders are stripped. Nothing of substance is removed.
- A `.p7s` signature or a calendar invite is skipped — it is not evidence of
  anything.

---

## 3. A separate tab for a generic draft

**What CEAT asked:** a separate tab for a generic draft.

**What was there before:** eight fixed notice types. Anything outside them had to
be forced into the nearest type and fought with the validator, or written from
nothing in Word.

**What was built.** A tenth type, **Generic draft**, deliberately loose: a short
question set (what the notice is called, who it goes to, the facts, what the
Company requires, by when, and what happens otherwise). It blocks on nothing but
the noticee's name and address. It still produces a proper CEAT notice —
letterhead, parties paragraph, numbered paragraphs, demand, reservation of
rights, signature block — and the long free-text answers get the same treatment
every other type's answers get: laid out as numbered paragraphs, lettered points,
or a table with a total where the lines carry amounts.

Two things keep it honest:

- The draft carries **"NON-STANDARD — FULL LEGAL REVIEW REQUIRED"** permanently.
  It is a drafting aid for a lawyer, not a notice the app's checks can clear.
- If the facts look like a matter one of the real types covers — a bounced
  cheque, a consumer notice, a termination, an infringement — the app says so and
  names the tab to use instead. The one way to misuse this tab is to pick it to
  avoid the questions a real type would ask.

In the sidebar it is marked ⚪ and sits last, below the 🟢 approved and 🟡
non-standard types.

---

## 4. The repeated table

**What CEAT asked:** repeated table in the notice — to be removed.

**Being straight about this one:** no table rendered twice in the code as it
stood. Two checks were run — every notice type against every test case looking
for a repeated table header or row, and all twelve notice documents shared during
this engagement, each of which had either no table or one. What *was* there, and
is almost certainly what CEAT reacted to, is the **same particulars appearing
twice in different forms**. From the Section 138 notice in CEAT's own files, the
invoice appeared three times: in the opening recital, in the invoice table, and
again in the part-discharge paragraph.

**What was built.** Two guarantees, both applied to every notice type:

1. **No two tables in a notice may carry the same references.** Where that
   happens the duplicate is dropped, and the typed table wins over one the app
   derived from prose, because the typed one has the columns the user chose to
   fill. If the sentence that introduced the dropped table was only there to
   introduce it, that sentence goes too — a notice saying "the particulars are
   set out below:" and then showing nothing would be worse than the repeat.
2. **A paragraph that merely re-lists what a table already shows now points at
   the table instead.** "The audit found that Invoice CEAT/A/1 dated 01.02.2026
   for INR 12,300 and Invoice CEAT/A/2 … were wrongly credited" becomes "The
   audit found that **the invoices set out in the Schedule below** were wrongly
   credited." The sentence keeps its meaning and its verb; only the enumeration
   goes.

This is deliberately narrow. It fires only on a sentence that lists **two or
more** of the very references the table carries and **nothing the table does not
cover** — anything looser would be rewriting the notice rather than
de-duplicating it. A notice without the repeat comes out byte-for-byte unchanged;
there is a test that asserts exactly that. And when it does fire, it says so in
Review notes rather than changing the notice silently.

The cross-reference also matches what the notice itself calls the table: a
recovery notice points at "the Statement of Account below", a termination notice
at "the Schedule below", a cheque notice at "the table below" — never at a
Schedule that appears nowhere in the document.

**Still worth asking CEAT for:** the notice where they saw it, with the repeat
circled. Their deployed copy is several rounds behind this code, so it is
possible they were looking at something already fixed.

---

## 5. Early payment discount

**What CEAT asked:** early payment discount to be included as a standard feature.

**What was there before:** nothing. No discount field existed anywhere.

**What was built.** A standard question — "Is an early payment discount being
offered, and until when?" — on the three notices that demand money: **Recovery,
Breach and Termination**. Give either a percentage or a flat sum, and the date
payment must reach the Company by. It can be typed in plain words: "5% if paid by
31.10.2026", "INR 25,000 off if paid within 10 days" (which is resolved to a real
date against the notice date).

**The discounted figure is calculated, never typed** — in figures and in words
through the same path as every other amount in the app, so it cannot disagree
with the principal on the page. That is the whole reason it is not just another
free-text answer.

The paragraph is a **without-prejudice settlement offer, not a reduction of the
debt**, and its wording lives in `skill/references/clause-library.md` like every
other paragraph, so CEAT's lawyers can edit it without touching code:

> Without prejudice to the Company's rights and remedies, and without in any
> manner admitting or reducing the liability stated above, the Company is willing
> to accept INR 7,98,000/- (Rupees Seven Lakh Ninety Eight Thousand Only) in full
> and final settlement of the aforesaid sum, being a reduction of INR 42,000/-
> (5%), provided the said amount is received by the Company on or before
> 14.10.2026. If the said amount is not so received, this offer shall stand
> withdrawn without further intimation and the Company's demand for the full sum
> of INR 8,40,000/-, together with interest, shall stand.

Six things are hard blocks, because a notice that demands one figure and offers a
lower one on terms that have already lapsed is worse than no offer at all:

| Situation | Why it is blocked |
|---|---|
| A discount on a **Section 138 notice** | The statutory demand must be for the cheque amount. Demanding or accepting less in the notice itself puts the notice at risk. Make the offer in a separate without-prejudice letter. |
| Both a percentage **and** a flat sum | Two discounts on the same sum cannot both be the offer. |
| A discount with no date | An open-ended offer never lapses and cannot be withdrawn cleanly. |
| A discount **at or above** the sum demanded | That is a waiver, not a discount. |
| A date on or before the notice date | It would be expired when the notice is served. |
| A date **after the demand period** | The offer would outlive the demand it is attached to. |

That last check reads the demand period **out of the drafted notice**, keyed to
"receipt of this notice" — so if someone shortens the demand from 15 days to 7,
the deadline the discount is measured against moves with it. (An earlier version
searched for the first "within N days" in the text and found the *30-day credit
term* in the recital instead. That is fixed and tested.)

Whenever a discount is offered, a note travels with the draft asking for the
offer and the figure to be confirmed before the notice goes out.

**What CEAT needs to decide:** the policy — fixed percentage or sliding scale,
who approves it, and whether it applies to Section 138 matters at all (the app
currently says no). And the sentence as their legal team wants it worded.

---

## 6. Cease and desist notice

**What CEAT asked:** include the Cease and Desist Notice.

**What was there before:** no such type. `SKILL.md` named cease-and-desist as its
example of "a notice type in neither table", so the skill could draft one in a
chat, but the console had no tab for it.

**What was built.** A full ninth notice type, with everything the other types
have:

- **`skill/references/cease-and-desist-notice.md`** — the paragraph-by-paragraph
  template and a nine-item checklist. Every paragraph the app writes is read from
  this file at runtime, so CEAT's lawyers change the wording by editing markdown.
- A question set: the right CEAT asserts and how it holds it; what the other side
  is doing, with particulars; each act that must stop; the period for a written
  undertaking; consequences.
- A drafting block producing: parties, the right asserted, the offending acts
  with the date CEAT noticed them, why the acts are actionable, **CEASE AND
  DESIST** from a lettered list of acts, a demand for a written undertaking,
  consequences, and reservation of rights.
- Its own checks in the validator.

Four details that took real work:

- **The subject line.** The answer about the right can run to a paragraph with
  registration numbers in it. The subject reduces it to "trade marks and trade
  name".
- **"Cease and desist from" takes a gerund.** People write these three ways —
  "ceasing all use of the marks", "use of the marks", "display the signage" — and
  all three used to break the sentence. Each is now normalised, and the acts are
  set out as a lettered list under a colon so compliance can be measured.
- **Particulars are checked, not assumed.** "You are infringing our trademarks"
  is flagged, not passed. The check looks for a place or a date in the facts.
- **A registered right with no registration number is flagged**, because that is
  the commonest way one of these notices gets answered with "prove it".

The checks assert against the **drafted notice**, not against whether the answer
boxes are filled — proved by patching the template so a paragraph loses its
content and watching the tick turn red while every answer box stays as it was.

**What CEAT needs to supply:** an approved cease-and-desist template or a past
sample, and a decision on whether it issues from CEAT directly or through their
advocates — that changes the closing and the signature block. Until then the
draft carries NON-STANDARD and a note saying the right asserted, the statute
relied on and the relief threatened are matters for counsel.

---

## Smaller things fixed along the way

These were found while testing the six above, and each has its own test.

- **A company with one director read "Mr. X, are its directors".** Now "is its
  director". Same for a partnership with one partner.
- **The generic notice borrowed the breach template's wording** and said "Should
  you fail to cure the breach" in a notice about a set-off.
- **"calls upon you to, within 15 days, acknowledge…"** put a comma between a
  verb and its infinitive. Now "calls upon you, within 15 days, to:".
- **Typing "You have failed to do so, in that …" into a termination's facts**
  produced it twice, because the template supplies that lead itself.
- **An empty `## Page footer` fence in `house-style.md`** matched the *next*
  fence further down the file, which would have put half of house-style.md across
  the bottom of every page.
- **Markdown emphasis leaked onto the page.** A reference file saying "Do **not**
  use this type…" printed the asterisks in the app's header.
- **The uploader's file-type list and the reader's were two separate lists** that
  could drift. An extension the uploader allowed but the reader did not know fell
  through to "decode as UTF-8" and produced a page of mojibake. They now come
  from one place.
- **`.msg` and `.eml` added to `.gitignore`** — an Outlook message dragged into
  the folder while testing is evidence in a live matter and must never reach
  GitHub.

---

## Dependency added

`olefile>=0.47` — pure Python, no compiled extension, so it installs on Streamlit
Cloud without a build step. It is what reads the Outlook `.msg` container.

(`extract-msg` is used instead *if* it happens to be installed, since it handles
rarer encodings, but it is not required and is not in `requirements.txt` — it
needs a C build that Streamlit Cloud will not do.)

---

## One thing on our side

**The deployed app is still several rounds behind this code.** Some of what CEAT
reported may already have been fixed. The current build should go up before the
next review, so their feedback is about the real state of the app.
