# CEAT Notice Drafting Console — Streamlit

The drafting console, with your CEAT skill as the backend rulebook rather than
a second copy of it. `skill/` is your skill folder dropped in whole: the ten
golden rules, the letterhead, the signatory block, the per-type templates and
required inputs are all **read out of those markdown files at runtime**. Edit
the skill, the app changes — no code edit.

## Run it

```bash
cd ceat-notice-app
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # then paste your Groq key into it
streamlit run app.py
```

Opens on http://localhost:8501.

### The key

Get one at <https://console.groq.com/keys>, then in `.env`:

```
GROQ_API_KEY=gsk_...
```

**Don't pin a model.** Hosted model IDs get retired — `llama-3.3-70b-versatile`
was shut down in August 2026 — so the app asks your key what it can actually
reach and picks the best available (`openai/gpt-oss-120b` for text,
`qwen/qwen3.6-27b` for images). If a call fails because an ID has just been
retired, it re-checks and retries once. The sidebar always shows which model is
in use. Set `GROQ_TEXT_MODEL` / `GROQ_VISION_MODEL` only to override that.

**It runs without a key.** Your typed answers are parsed directly, and
spreadsheets, CSVs, PDFs and Word files are read deterministically — header-row
detection, column sniffing, row filtering by the party you named, totals. What
the key adds is genuine reasoning over messy input, and reading **cheque photos
and scans** through the vision model.

To use an OpenAI-compatible endpoint instead, set `LLM_PROVIDER=openai` and the
`OPENAI_*` variables. Nothing else changes — Groq speaks the same protocol.

### If it won't start

**`No secrets found. Valid paths for a secrets.toml file...`** — this app never reads
`st.secrets`, so that error means Streamlit is running a *different* `app.py`. Check the
folder named in the error message: run from inside `ceat-notice-app/`, where `app.py`
sits next to `core/` and `skill/`. `streamlit run app.py` picks up whatever is in the
current directory.

**`Groq connected` never appears** — `.env` must sit beside `app.py`. On Windows,
Notepad silently saves it as `.env.txt`; turn on file-name extensions to check. The line
is `GROQ_API_KEY=gsk_...` with no spaces and no quotes.

## Three ways in, mix them freely

1. **Tell it the whole matter** — one box at the top, brief it the way you would
   brief a colleague. It reads the cheques, dates, amounts, bank, party, mode and
   signatory straight out of the prose and fills the questions below.
2. **Answer the questions** — one flat list, none of it compulsory.
3. **Attach what you have** — Excel, CSV, PDF, Word, JPG, PNG, against any question.

They stack. Anything you answer specifically beats the general account; both beat
what is read out of a file. Nothing overwrites something you typed yourself.

The narrative reader is cue-anchored — it takes a value because the text names it
("drawn on", "as on", "dishonoured", "Drawer:"), never because of where it sits.
With a model key the same text also goes to the model, which reads messier prose
than any regex can.

## The flow

```
tell it the whole matter  /  answer what you can  →  attach whatever you have
        ↓
press “Analyse everything and draft the notice”
        ↓
every document is read; what you already typed is used to find the right
material in it (name the dealer, only that dealer's rows are taken)
        ↓
values are applied — never over anything you typed, never invented
        ↓
validate: arithmetic, dates, the reference file's mandatory checklist
        ↓
blocked?  →  it does not draft. It names exactly what is missing.
holds?    →  the notice is drafted; anything optional shows as [● ...]
```

Nothing is drafted until the button is pressed. Any edit afterwards
un-drafts it, so a change always goes back through the checks.

## What's where

| | |
|---|---|
| `app.py` | the Streamlit UI — one flat question list per notice type |
| `core/skill_loader.py` | parses `skill/**.md` — rules, letterhead, templates, checklists |
| `core/schema.py` | the questions, the field model, the critical sets |
| `core/extract.py` | file → text / tables / image. pandas, pdfplumber, python-docx |
| `core/analyse.py` | the model call, plus a deterministic reader as the floor |
| `core/validate.py` | blockers, flags, the per-type checklist |
| `core/draft.py` | approved wording → text and a real `.docx` |
| `core/freetext.py` | reads fields out of typed answers and out of a whole-matter account |
| `core/models.py` | asks the provider which models exist and picks one |
| `core/words.py` | Indian numbering, amounts in words, DD.MM.YYYY |
| `.streamlit/config.toml` | the pinned theme — same look on every machine |

## The screen

- **Readiness meter** — how much of this notice type is answered, how many
  documents are attached, and whether anything essential is still outstanding.
- **Filter** — *Everything*, *Not yet answered*, *Essential only*. Nothing is
  compulsory; the filter is for finding what's left, not for nagging.
- A **dot** on each question: filled, partly filled, open.
- **Draft · Review notes · Checklist · All fields · History · Rules** down the
  right, and the panel follows you as you scroll the questions.
  - *All fields* lists every field the notice can carry and exactly what is
    held against each — a blank is shown as a blank.
  - *History* keeps every notice drafted this session; restore one to pick it
    back up, or take the text without leaving the page.
  - *Rules* is the ten non-negotiables, read live from `SKILL.md`.
  - *Review notes* also has a notepad that never enters the document.

## The rules it enforces

Straight from `SKILL.md`, in two layers — the model is instructed, and then
everything it returns is re-checked in code:

- **Never invent.** No value that isn't in your input or a document. Missing
  stays missing and renders as `[● ...]` in the draft.
- **No provision from memory.** Statutory wording comes from the templates; every
  draft carries a VERIFY note to check against India Code or India Kanoon.
- **Arithmetic ties.** Cheque total vs the demand; statement of account vs the
  demand; principal + GST vs the total. A mismatch is a blocker, not a warning.
- **Figures and words agree.** Editing one without the other blocks the draft.
- **Document vs chat.** The `.docx` is the notice only. Flags, annexures and the
  review banner live in the Review notes tab and never enter the file.
- **Every output is a draft** for a qualified lawyer.

## Notes on the Streamlit specifics

The things that usually break a Streamlit app of this shape, and how they're handled:

- **Reruns wiping state** — everything mutable lives in `st.session_state.case[kind]`;
  widgets have stable keys; values are read back and compared, never assigned into
  session state after the widget exists.
- **Re-parsing uploads on every keystroke** — files are parsed once and cached by
  SHA-256 digest in `st.session_state.parsed`.
- **The draft flickering as you type** — it doesn't render at all until the button
  is pressed, and any edit invalidates it.
- **Per-notice-type isolation** — switching type in the sidebar keeps each case,
  its documents and its draft separate.

## Handling real notices

Case data lives in the Streamlit session only — nothing is written to disk unless
you download it. Run it on your own machine or an internal server; don't put live
matters on Streamlit Community Cloud. Clear the case when the matter is done.
