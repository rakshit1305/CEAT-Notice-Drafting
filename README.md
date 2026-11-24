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

That is the whole install without a database. To keep matters and notices, and
give each person their own sign-in, add one line to `.env` — see
[Database and sign-in](#database-and-sign-in).

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

### Azure OpenAI

`LLM_PROVIDER` chooses the provider per machine — `groq` (default), `openai`,
or `azure` — so a laptop can stay on Groq while the server runs CEAT's Azure
resource from the same code. The Azure settings are the ones `ceat-compintel`
uses, so its block can be pasted in unchanged:

```
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_TEXT_DEPLOYMENT=<deployment that reads and writes text>
AZURE_VISION_DEPLOYMENT=<deployment that reads images>
```

- **Deployment names, not model ids.** Azure calls whatever you named the
  deployment in the portal. The app uses the name exactly as set and never
  substitutes another — a wrong name is a `404 DeploymentNotFound`, shown as it is.
- **Which deployment.** `AZURE_TEXT_DEPLOYMENT` if set; otherwise
  `AZURE_TIER2_DEPLOYMENT`, then `AZURE_TIER1_DEPLOYMENT` (the `ceat-compintel`
  names). `AZURE_VISION_DEPLOYMENT` defaults to the text one.
- **Either endpoint form.** The bare resource host (uses the API version) or
  one ending in `/openai/v1` (does not). The app tells them apart from the URL.
- **Rate limits.** Azure meters tokens per minute per deployment, so a 429 is
  waited out and retried — as long as Azure says, up to `LLM_MAX_RETRIES` (5)
  times — instead of dropping to deterministic reading. Timeout 120 s.
- **Temperature** is not sent on Azure: the gpt-5.x family accepts only the
  default, so replies vary a little more between runs there.
- **Cost.** Azure reports tokens, never a price. Set `LLM_PRICE_TABLE` to have
  `llm_calls.cost_usd` filled in.

The sidebar shows the provider, the deployments in use, and names any setting
that is still missing.

### If it won't start

**`No secrets found. Valid paths for a secrets.toml file...`** — this app never reads
`st.secrets`, so that error means Streamlit is running a *different* `app.py`. Check the
folder named in the error message: run from inside `ceat-notice-app/`, where `app.py`
sits next to `core/` and `skill/`. `streamlit run app.py` picks up whatever is in the
current directory.

**`Groq connected` never appears** — `.env` must sit beside `app.py`. On Windows,
Notepad silently saves it as `.env.txt`; turn on file-name extensions to check. The line
is `GROQ_API_KEY=gsk_...` with no spaces and no quotes.

## Database and sign-in

Optional. Point the app at a Postgres server and it keeps everything there
instead of in the browser session:

```
DATABASE_URL=postgresql://ceat:your_db_password@localhost:5432/ceat_notices
```

Nothing else to run. On first start the app creates the `ceat_notices` database
if the server does not have it, creates the tables from `db/schema.sql`, and
adds the first admin account. It is a separate database from `ceat_compintel`
on the same server — the two share nothing.

### The same keys as ceat-compintel

Instead of one address, the connection can be given as the pieces
`ceat-compintel` uses, so the Postgres block of its `.env` carries over with one
line changed — the database name:

```
POSTGRES_USER=ceat
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=ceat_notices
DB_HOST=localhost
DB_PORT=5433
```

| Key | What it is |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | The role the app signs in to Postgres with. It can be the one `ceat-compintel` uses. |
| `POSTGRES_DB` | This app's database. Defaults to `ceat_notices`. |
| `DB_HOST`, `DB_PORT` | The server. `POSTGRES_HOST` and `POSTGRES_PORT` are read too; the port defaults to 5432. |
| `DB_SSL_PARAMS` | Optional, for a server that requires TLS — for example `sslmode=verify-full&sslrootcert=/etc/ssl/ceat/ca.crt`. |
| `DB_WAN_PARAMS` | Optional timeouts and keep-alives for a server reached over the internet. |
| `DATABASE_URL_LOCAL` | Read as another name for `DATABASE_URL`. |

`DATABASE_URL` wins if it is set as well. Where the server is depends on where
`ceat-compintel`'s Postgres runs:

- **Its dev stack on this machine** (`docker compose up`): `localhost`, port
  `5433`, role `ceat`. That role is the superuser there, so the app creates
  `ceat_notices` by itself.
- **The shared database server** (`deploy/db-shared`): the server's private
  address, port `5432`. The `ceat` role cannot create databases there, so the
  server's administrator runs `db/bootstrap.sql` once, as `postgres`. It creates
  `ceat_notices` owned by `ceat` and closes it to every other role.
- **The hardened database server** (`deploy/db-server`): as above, and its
  `pg_hba.conf` also names each database the app server may reach — add a
  `hostssl ceat_notices ceat <app server address>/32 scram-sha-256` line beside
  the `ceat_compintel` one. Use the direct port (`7000`); the pooled port only
  knows the two `ceat_compintel` databases.

The role and the server can be shared; the database cannot. Pointed at
`ceat_compintel` (or any database that already has another application's
tables), the app stops with a message instead of creating its tables there —
both projects have tables called `app_users` and `llm_calls`.

### First sign-in

| | |
|---|---|
| Email | `admin@ceat.com` |
| Password | `ChangeMe@123` |

You are made to choose a new password before anything opens, and the default
is refused as a new password. The account is created only when there are no
accounts at all, so it does not come back after you replace or delete it. To
start with different details, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`
**before** the first start — do this on anything reachable from the internet.
(`SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD` and `SESSION_TTL_HOURS`, the
`ceat-compintel` names, are accepted as well.)

### Adding people — the admin page

There is no self-signup. Sign in as an admin and press **Manage users** in the
sidebar:

- **Add a person** — their email, a role, and a temporary password (leave it
  blank and one is generated and shown once). They choose their own at first
  sign-in.
- **Change an account** — make someone an admin or a user, untick *Can sign in*
  to deactivate them, or set a new temporary password. Deactivating or
  resetting signs that person out on their next click.
- **Delete this account** — the matters and notices they made stay.
- **Model usage** — model calls and tokens per person over the last 30 days.

Two roles: **admin** can open this page, **user** can only draft. You cannot
deactivate, demote or delete yourself, or the only active admin, so the console
can never be left without one. Anyone can change their own password from the
sidebar. Five wrong passwords in a row lock that email for fifteen minutes.

### What is kept

| Table | What |
|---|---|
| `matters` | Your working case for each notice type, saved as you type and back when you sign in again. *Clear this case* closes it and starts a new one. |
| `matter_documents` | Every attachment — the file itself and what was read out of it. |
| `notices` | Every notice that passed its checks, and every version downloaded: the text, the `.docx`, the answers behind it and the review notes. This is the **History** tab, shared by everyone who signs in. Nothing is overwritten; an identical notice is stored once. |
| `offices` | The issuing offices. An existing `offices.json` is carried over the first time. |
| `llm_calls` | One row per model call — who, which matter, tokens, time taken. |
| `app_users`, `app_sessions` | Accounts (passwords as salted PBKDF2 hashes) and sign-ins. |

Signing in lasts for the browser tab: refresh the page and you sign in again,
and your matter is as you left it. Sign-ins expire after 12 hours
(`SESSION_HOURS`).

Schema changes go in `db/migrations/002_*.sql` onwards, written so they can run
twice; the app applies them in name order at every start.

With no database configured none of this applies: the app runs in the session,
and `APP_PASSWORD` sets one shared password for everyone.

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
| `core/db.py` | the Postgres connection; creates the database and tables on first use |
| `core/auth.py` | accounts, password hashing, sign-in sessions |
| `core/store.py` | matters, attachments and the notice register |
| `core/admin_page.py` | the admin page — who can sign in |
| `db/schema.sql` | the tables, one comment per table saying what it replaces |
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
    back up, or take the text without leaving the page. With a database it is
    the shared register of every notice drafted, with the stored `.docx`.
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

Without a database, case data lives in the Streamlit session only — nothing is
written to disk unless you download it. With one, matters, attachments and
drafted notices are kept in Postgres until someone removes them: that database
holds party names, addresses, cheque details and the documents themselves, so
back it up and restrict access to it the way you would the files.

Run it on your own machine or an internal server; don't put live matters on
Streamlit Community Cloud. Serve it over HTTPS if it is reachable beyond your
own machine — sign-in sends the password to the server.
